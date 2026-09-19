"""Evaluation traces — lifecycle observability tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.judge.errors import JudgeEvaluationError
from app.judge.provider import FakeLLMJudgeProvider, clear_judge_provider_override, set_judge_provider_override
from app.traces.events import TraceEventType
from app.traces.sanitize import sanitize_trace_data


@pytest.fixture(autouse=True)
def _clear_provider():
    clear_judge_provider_override()
    yield
    clear_judge_provider_override()


SAMPLE_CASES = [
    {
        "external_id": "t1",
        "input": {"question": "Capital?"},
        "expected": {"answer": "Paris"},
        "metadata": {},
        "tags": [],
    },
    {
        "external_id": "t2",
        "input": {"question": "2+2?"},
        "expected": {"answer": "4"},
        "metadata": {},
        "tags": [],
    },
]


async def _setup(client: AsyncClient) -> dict:
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": f"trace-{uuid4().hex[:8]}@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
    project = await client.post("/api/v1/projects", headers=headers, json={"name": "Traces"})
    project_id = project.json()["id"]
    dataset = await client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=headers,
        json={"name": "DS"},
    )
    version = await client.post(
        f"/api/v1/datasets/{dataset.json()['id']}/versions",
        headers=headers,
        json={"test_cases": SAMPLE_CASES},
    )
    cases = await client.get(
        f"/api/v1/dataset-versions/{version.json()['id']}/test-cases",
        headers=headers,
    )
    case_map = {c["external_id"]: c["id"] for c in cases.json()}
    return {
        "headers": headers,
        "project_id": project_id,
        "version_id": version.json()["id"],
        "case_map": case_map,
    }


async def _complete_run(client: AsyncClient, ctx: dict, *, metrics: list[str] | None = None) -> str:
    created = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={
            "dataset_version_id": ctx["version_id"],
            "metrics": metrics or ["exact_match", "string_similarity"],
        },
    )
    assert created.status_code == 201
    run_id = created.json()["id"]
    submit = await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=ctx["headers"],
        json={
            "results": [
                {"test_case_id": ctx["case_map"]["t1"], "actual_output": {"answer": "Paris"}},
                {"test_case_id": ctx["case_map"]["t2"], "actual_output": {"answer": "4"}},
            ]
        },
    )
    assert submit.status_code == 200
    assert submit.json()["run"]["status"] == "COMPLETED"
    return run_id


def test_sanitize_strips_secrets() -> None:
    cleaned = sanitize_trace_data(
        {
            "provider": "openai_compatible",
            "api_key": "sk-secret",
            "Authorization": "Bearer sk-secret",
            "nested": {"judge_api_key": "x", "model": "m"},
        }
    )
    assert "api_key" not in cleaned
    assert "Authorization" not in cleaned
    assert "judge_api_key" not in cleaned["nested"]
    assert cleaned["nested"]["model"] == "m"
    assert cleaned["provider"] == "openai_compatible"


@pytest.mark.asyncio
async def test_run_lifecycle_and_metric_traces(client: AsyncClient) -> None:
    ctx = await _setup(client)
    run_id = await _complete_run(client, ctx)

    traces = await client.get(f"/api/v1/runs/{run_id}/traces", headers=ctx["headers"])
    assert traces.status_code == 200
    body = traces.json()
    assert body["run_id"] == run_id
    types = [e["event_type"] for e in body["events"]]
    assert types[0] == TraceEventType.RUN_STARTED.value
    assert types[-1] == TraceEventType.RUN_COMPLETED.value
    assert types.count(TraceEventType.CASE_STARTED.value) == 2
    assert types.count(TraceEventType.CASE_COMPLETED.value) == 2
    assert TraceEventType.METRIC_EVALUATION.value in types
    assert TraceEventType.MODEL_CALL.value not in types  # no llm_judge

    # Chronological ordering
    timestamps = [e["timestamp"] for e in body["events"]]
    assert timestamps == sorted(timestamps)

    # Metric events have score
    metric_events = [e for e in body["events"] if e["event_type"] == "metric_evaluation"]
    assert any(e["data"].get("metric") == "string_similarity" for e in metric_events)
    assert all("score" in e["data"] for e in metric_events)
    # No secrets
    blob = str(body)
    assert "api_key" not in blob.lower() or "api_key" not in str(
        [e["data"] for e in body["events"]]
    ).lower()


@pytest.mark.asyncio
async def test_case_traces_scoped_and_run_includes_all(client: AsyncClient) -> None:
    ctx = await _setup(client)
    run_id = await _complete_run(client, ctx)
    cases = await client.get(f"/api/v1/runs/{run_id}/results", headers=ctx["headers"])
    case_ids = [c["id"] for c in cases.json()]
    assert len(case_ids) == 2

    case_a = await client.get(
        f"/api/v1/runs/{run_id}/cases/{case_ids[0]}/traces",
        headers=ctx["headers"],
    )
    assert case_a.status_code == 200
    events_a = case_a.json()["events"]
    assert case_a.json()["case_result_id"] == case_ids[0]
    assert all(e["case_result_id"] == case_ids[0] for e in events_a)
    assert TraceEventType.RUN_STARTED.value not in [e["event_type"] for e in events_a]

    run_traces = await client.get(f"/api/v1/runs/{run_id}/traces", headers=ctx["headers"])
    case_result_ids = {
        e["case_result_id"] for e in run_traces.json()["events"] if e["case_result_id"]
    }
    assert set(case_ids) == case_result_ids


@pytest.mark.asyncio
async def test_model_call_with_and_without_tokens(client: AsyncClient) -> None:
    ctx = await _setup(client)

    set_judge_provider_override(
        FakeLLMJudgeProvider(
            '{"score": 0.9, "reason": "ok"}',
            latency_ms=42.5,
            input_tokens=120,
            output_tokens=65,
            total_tokens=185,
        )
    )
    run_with = await _complete_run(client, ctx, metrics=["llm_judge"])
    traces = await client.get(f"/api/v1/runs/{run_with}/traces", headers=ctx["headers"])
    model_calls = [e for e in traces.json()["events"] if e["event_type"] == "model_call"]
    assert model_calls
    assert model_calls[0]["data"]["provider"] == "fake"
    assert model_calls[0]["data"]["latency_ms"] == pytest.approx(42.5)
    assert model_calls[0]["data"]["input_tokens"] == 120
    assert model_calls[0]["data"]["output_tokens"] == 65
    assert model_calls[0]["data"]["total_tokens"] == 185
    assert "api_key" not in model_calls[0]["data"]

    metric_judge = [
        e
        for e in traces.json()["events"]
        if e["event_type"] == "metric_evaluation" and e["data"].get("metric") == "llm_judge"
    ]
    assert metric_judge
    assert metric_judge[0]["data"]["provider"] == "fake"
    assert "reason" in metric_judge[0]["data"]

    # Missing token usage — fields absent
    set_judge_provider_override(
        FakeLLMJudgeProvider('{"score": 0.8, "reason": "ok"}', latency_ms=10.0)
    )
    run_without = await _complete_run(client, ctx, metrics=["llm_judge"])
    traces2 = await client.get(f"/api/v1/runs/{run_without}/traces", headers=ctx["headers"])
    call = next(e for e in traces2.json()["events"] if e["event_type"] == "model_call")
    assert "input_tokens" not in call["data"]
    assert "output_tokens" not in call["data"]
    assert "total_tokens" not in call["data"]
    assert call["data"]["latency_ms"] == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_case_failed_error_trace(client: AsyncClient) -> None:
    set_judge_provider_override(FakeLLMJudgeProvider(JudgeEvaluationError("timed out")))
    ctx = await _setup(client)
    created = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={"dataset_version_id": ctx["version_id"], "metrics": ["llm_judge"]},
    )
    run_id = created.json()["id"]
    await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=ctx["headers"],
        json={
            "results": [
                {"test_case_id": ctx["case_map"]["t1"], "actual_output": {"answer": "Paris"}},
                {"test_case_id": ctx["case_map"]["t2"], "actual_output": {"answer": "4"}},
            ]
        },
    )
    traces = await client.get(f"/api/v1/runs/{run_id}/traces", headers=ctx["headers"])
    types = [e["event_type"] for e in traces.json()["events"]]
    assert TraceEventType.CASE_FAILED.value in types
    assert TraceEventType.RUN_COMPLETED.value in types  # run still completes
    failed = next(e for e in traces.json()["events"] if e["event_type"] == "case_failed")
    assert "message" in failed["data"]
    assert "api_key" not in str(failed["data"]).lower()


@pytest.mark.asyncio
async def test_client_error_case_failed(client: AsyncClient) -> None:
    ctx = await _setup(client)
    created = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={"dataset_version_id": ctx["version_id"], "metrics": ["exact_match"]},
    )
    run_id = created.json()["id"]
    await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=ctx["headers"],
        json={
            "results": [
                {
                    "test_case_id": ctx["case_map"]["t1"],
                    "error_message": "model crashed",
                },
                {"test_case_id": ctx["case_map"]["t2"], "actual_output": {"answer": "4"}},
            ]
        },
    )
    traces = await client.get(f"/api/v1/runs/{run_id}/traces", headers=ctx["headers"])
    failed = [e for e in traces.json()["events"] if e["event_type"] == "case_failed"]
    assert len(failed) == 1
    assert "model crashed" in failed[0]["data"]["message"]


@pytest.mark.asyncio
async def test_trace_ownership_isolation(client: AsyncClient) -> None:
    ctx_a = await _setup(client)
    run_id = await _complete_run(client, ctx_a)

    other = await client.post(
        "/api/v1/auth/register",
        json={"email": f"other-{uuid4().hex[:8]}@example.com", "password": "password123"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    denied = await client.get(f"/api/v1/runs/{run_id}/traces", headers=other_headers)
    assert denied.status_code == 403

    cases = await client.get(f"/api/v1/runs/{run_id}/results", headers=ctx_a["headers"])
    case_id = cases.json()[0]["id"]
    denied_case = await client.get(
        f"/api/v1/runs/{run_id}/cases/{case_id}/traces",
        headers=other_headers,
    )
    assert denied_case.status_code == 403


@pytest.mark.asyncio
async def test_case_not_on_run_404(client: AsyncClient) -> None:
    ctx = await _setup(client)
    run_id = await _complete_run(client, ctx)
    missing = await client.get(
        f"/api/v1/runs/{run_id}/cases/{uuid4()}/traces",
        headers=ctx["headers"],
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_traces_append_only_no_mutation_endpoints(client: AsyncClient) -> None:
    ctx = await _setup(client)
    run_id = await _complete_run(client, ctx)
    traces = await client.get(f"/api/v1/runs/{run_id}/traces", headers=ctx["headers"])
    event_id = traces.json()["events"][0]["id"]

    for method in ("put", "patch", "delete"):
        url = f"/api/v1/runs/{run_id}/traces/{event_id}"
        if method == "delete":
            response = await client.delete(url, headers=ctx["headers"])
        else:
            response = await getattr(client, method)(
                url,
                headers=ctx["headers"],
                json={"data": {"hacked": True}},
            )
        assert response.status_code in {404, 405}

    # Re-fetch unchanged
    again = await client.get(f"/api/v1/runs/{run_id}/traces", headers=ctx["headers"])
    assert again.json()["events"][0]["data"] == traces.json()["events"][0]["data"]


@pytest.mark.asyncio
async def test_run_started_once_across_batches(client: AsyncClient) -> None:
    ctx = await _setup(client)
    created = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={"dataset_version_id": ctx["version_id"], "metrics": ["exact_match"]},
    )
    run_id = created.json()["id"]
    await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=ctx["headers"],
        json={
            "results": [
                {"test_case_id": ctx["case_map"]["t1"], "actual_output": {"answer": "Paris"}},
            ]
        },
    )
    await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=ctx["headers"],
        json={
            "results": [
                {"test_case_id": ctx["case_map"]["t2"], "actual_output": {"answer": "4"}},
            ]
        },
    )
    traces = await client.get(f"/api/v1/runs/{run_id}/traces", headers=ctx["headers"])
    types = [e["event_type"] for e in traces.json()["events"]]
    assert types.count(TraceEventType.RUN_STARTED.value) == 1
    assert types.count(TraceEventType.RUN_COMPLETED.value) == 1
