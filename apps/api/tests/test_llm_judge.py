"""LLM-as-a-judge metric tests — all provider calls are mocked (no network)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.judge.errors import JudgeEvaluationError
from app.judge.metric import LLMJudgeMetric
from app.judge.parsing import parse_judge_response
from app.judge.provider import (
    FakeLLMJudgeProvider,
    OpenAICompatibleJudgeProvider,
    clear_judge_provider_override,
    set_judge_provider_override,
)
from app.metrics.registry import MetricContext, MetricRegistry
from app.regression.engine import RegressionService
from app.core.models import CaseResult, CaseResultStatus, EvaluationRun, RegressionPolicy, RunStatus


@pytest.fixture(autouse=True)
def _clear_provider_override():
    clear_judge_provider_override()
    yield
    clear_judge_provider_override()


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_parse_valid_json() -> None:
    score, reason = parse_judge_response('{"score": 0.91, "reason": "Aligned"}')
    assert score == pytest.approx(0.91)
    assert reason == "Aligned"


def test_parse_markdown_fenced_json() -> None:
    raw = 'Here is the result:\n```json\n{"score": 0.85, "reason": "Mostly correct"}\n```\n'
    score, reason = parse_judge_response(raw)
    assert score == pytest.approx(0.85)
    assert "Mostly" in reason


def test_parse_malformed_response() -> None:
    with pytest.raises(JudgeEvaluationError, match="JSON"):
        parse_judge_response("not json at all")


def test_parse_missing_score() -> None:
    with pytest.raises(JudgeEvaluationError, match="score"):
        parse_judge_response('{"reason": "ok"}')


def test_parse_score_below_zero() -> None:
    with pytest.raises(JudgeEvaluationError, match="outside"):
        parse_judge_response('{"score": -0.1, "reason": "bad"}')


def test_parse_score_above_one() -> None:
    with pytest.raises(JudgeEvaluationError, match="outside"):
        parse_judge_response('{"score": 1.5, "reason": "bad"}')


def test_parse_non_numeric_score() -> None:
    with pytest.raises(JudgeEvaluationError, match="numeric"):
        parse_judge_response('{"score": "high", "reason": "bad"}')


def test_parse_nan_rejected() -> None:
    from app.judge.parsing import _validate_score

    with pytest.raises(JudgeEvaluationError, match="finite"):
        _validate_score(float("nan"))
    with pytest.raises(JudgeEvaluationError, match="finite"):
        _validate_score(float("inf"))


# ---------------------------------------------------------------------------
# Metric + provider
# ---------------------------------------------------------------------------


def test_llm_judge_in_registry() -> None:
    assert MetricRegistry.has("llm_judge")
    assert "llm_judge" in MetricRegistry.list_metrics()


def test_valid_judge_score_and_reason() -> None:
    set_judge_provider_override(
        FakeLLMJudgeProvider('{"score": 0.95, "reason": "Semantically equivalent."}')
    )
    result = LLMJudgeMetric().score(
        {"answer": "France's capital city is Paris."},
        {"answer": "Paris is the capital of France."},
        MetricContext(input={"question": "Capital of France?"}),
    )
    assert result.score == pytest.approx(0.95)
    assert result.passed is True
    assert "Semantically" in (result.reason or "")


def test_provider_timeout_surfaces_as_error() -> None:
    set_judge_provider_override(FakeLLMJudgeProvider(JudgeEvaluationError("Judge provider request timed out")))
    with pytest.raises(JudgeEvaluationError, match="timed out"):
        LLMJudgeMetric().score({"a": 1}, {"a": 1}, MetricContext(input={}))


def test_openai_compatible_requires_api_key() -> None:
    provider = OpenAICompatibleJudgeProvider(
        api_key=None,
        model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
    )
    with pytest.raises(JudgeEvaluationError, match="API_KEY"):
        provider.complete("prompt")


def test_deterministic_metrics_ignore_context() -> None:
    em = MetricRegistry.get("exact_match").score(
        {"answer": "yes"},
        {"answer": "yes"},
        MetricContext(input={"q": 1}),
    )
    assert em.score == 1.0
    assert em.reason is None


# ---------------------------------------------------------------------------
# API integration
# ---------------------------------------------------------------------------

SAMPLE_CASES = [
    {
        "external_id": "j1",
        "input": {"question": "Capital of France?"},
        "expected": {"answer": "Paris is the capital of France."},
        "metadata": {},
        "tags": [],
    },
    {
        "external_id": "j2",
        "input": {"question": "2+2?"},
        "expected": {"answer": "4"},
        "metadata": {},
        "tags": [],
    },
]


async def _setup(client: AsyncClient) -> dict:
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": f"judge-{uuid4().hex[:8]}@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
    project = await client.post("/api/v1/projects", headers=headers, json={"name": "Judge"})
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
    case_map = {c["external_id"]: c["id"] for c in cases.json()["items"]}
    exp = await client.post(
        f"/api/v1/projects/{project_id}/experiments",
        headers=headers,
        json={"name": "Judge Exp"},
    )
    return {
        "headers": headers,
        "project_id": project_id,
        "version_id": version.json()["id"],
        "case_map": case_map,
        "experiment_id": exp.json()["id"],
    }


@pytest.mark.asyncio
async def test_run_with_llm_judge_stores_score_and_reason(client: AsyncClient) -> None:
    set_judge_provider_override(
        FakeLLMJudgeProvider('{"score": 0.91, "reason": "The response is factually aligned with the reference..."}')
    )
    ctx = await _setup(client)
    created = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={
            "experiment_id": ctx["experiment_id"],
            "dataset_version_id": ctx["version_id"],
            "metrics": ["exact_match", "string_similarity", "llm_judge"],
            "config_snapshot": {"model": "demo"},
        },
    )
    assert created.status_code == 201
    run_id = created.json()["id"]

    detail = await client.get(f"/api/v1/runs/{run_id}", headers=ctx["headers"])
    snap = detail.json()["config_snapshot"]
    assert snap["metrics"] == ["exact_match", "string_similarity", "llm_judge"]
    assert "judge" in snap
    assert snap["judge"]["provider"] == "openai_compatible"
    assert "api_key" not in snap
    assert "api_key" not in snap["judge"]
    assert "JUDGE_API_KEY" not in str(snap)

    submit = await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=ctx["headers"],
        json={
            "results": [
                {
                    "test_case_id": ctx["case_map"]["j1"],
                    "actual_output": {"answer": "France's capital city is Paris."},
                },
                {
                    "test_case_id": ctx["case_map"]["j2"],
                    "actual_output": {"answer": "4"},
                },
            ]
        },
    )
    assert submit.status_code == 200
    assert submit.json()["run"]["status"] == "COMPLETED"
    aggregates = submit.json()["run"]["metric_aggregates"]
    assert "llm_judge" in aggregates
    assert aggregates["llm_judge"]["average"] == pytest.approx(0.91)

    cases = await client.get(f"/api/v1/runs/{run_id}/results", headers=ctx["headers"])
    assert cases.status_code == 200
    for row in cases.json()["items"]:
        lj = row["metric_scores"]["llm_judge"]
        assert lj["score"] == pytest.approx(0.91)
        assert "factually aligned" in lj["reason"]
        assert "score" in row["metric_scores"]["exact_match"]


@pytest.mark.asyncio
async def test_judge_failure_marks_case_failed_not_run(client: AsyncClient) -> None:
    set_judge_provider_override(FakeLLMJudgeProvider(JudgeEvaluationError("invalid JSON")))
    ctx = await _setup(client)
    created = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={
            "dataset_version_id": ctx["version_id"],
            "metrics": ["llm_judge"],
        },
    )
    run_id = created.json()["id"]
    submit = await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=ctx["headers"],
        json={
            "results": [
                {"test_case_id": ctx["case_map"]["j1"], "actual_output": {"answer": "Paris"}},
                {"test_case_id": ctx["case_map"]["j2"], "actual_output": {"answer": "4"}},
            ]
        },
    )
    body = submit.json()["run"]
    assert body["status"] == "COMPLETED"
    assert body["failed_cases"] == 2
    cases = await client.get(f"/api/v1/runs/{run_id}/results", headers=ctx["headers"])
    for row in cases.json()["items"]:
        assert row["status"] == "FAILED"
        assert "llm_judge" in (row["error_message"] or "")
        assert "llm_judge" not in row["metric_scores"]


@pytest.mark.asyncio
async def test_llm_judge_regression_policy(client: AsyncClient) -> None:
    # Baseline high, current low — regression FAIL on llm_judge
    set_judge_provider_override(FakeLLMJudgeProvider('{"score": 0.95, "reason": "good"}'))
    ctx = await _setup(client)

    async def complete(score_json: str) -> str:
        set_judge_provider_override(FakeLLMJudgeProvider(score_json))
        created = await client.post(
            f"/api/v1/projects/{ctx['project_id']}/runs",
            headers=ctx["headers"],
            json={
                "experiment_id": ctx["experiment_id"],
                "dataset_version_id": ctx["version_id"],
                "metrics": ["llm_judge"],
            },
        )
        run_id = created.json()["id"]
        await client.post(
            f"/api/v1/runs/{run_id}/results",
            headers=ctx["headers"],
            json={
                "results": [
                    {"test_case_id": ctx["case_map"]["j1"], "actual_output": {"answer": "Paris"}},
                    {"test_case_id": ctx["case_map"]["j2"], "actual_output": {"answer": "4"}},
                ]
            },
        )
        return run_id

    baseline_id = await complete('{"score": 0.95, "reason": "good"}')
    await client.post(
        f"/api/v1/experiments/{ctx['experiment_id']}/baseline/{baseline_id}",
        headers=ctx["headers"],
    )
    await client.post(
        f"/api/v1/experiments/{ctx['experiment_id']}/regression-policies",
        headers=ctx["headers"],
        json={"metric_name": "llm_judge", "max_allowed_drop": 0.05},
    )
    current_id = await complete('{"score": 0.70, "reason": "weaker"}')
    result = await client.post(
        f"/api/v1/runs/{current_id}/evaluate-regression",
        headers=ctx["headers"],
    )
    assert result.status_code == 200
    assert result.json()["regression"]["status"] == "FAIL"
    assert result.json()["regression"]["aggregate"]["llm_judge"]["violated"] is True
    detail = await client.get(f"/api/v1/runs/{current_id}", headers=ctx["headers"])
    assert detail.json()["status"] == "COMPLETED"
    assert detail.json()["regression_status"] == "FAIL"


def test_engine_compares_llm_judge_numeric_scores() -> None:
    tid = uuid4()
    run_id = uuid4()
    current = EvaluationRun(
        id=run_id,
        project_id=uuid4(),
        dataset_version_id=uuid4(),
        status=RunStatus.COMPLETED.value,
        config_snapshot={},
    )
    baseline = EvaluationRun(
        id=uuid4(),
        project_id=current.project_id,
        dataset_version_id=current.dataset_version_id,
        status=RunStatus.COMPLETED.value,
        config_snapshot={},
    )
    baseline_cr = CaseResult(
        run_id=baseline.id,
        test_case_id=tid,
        status=CaseResultStatus.COMPLETED.value,
        metric_scores={"llm_judge": {"score": 0.94, "passed": True, "reason": "good"}},
    )
    current_cr = CaseResult(
        run_id=current.id,
        test_case_id=tid,
        status=CaseResultStatus.COMPLETED.value,
        metric_scores={"llm_judge": {"score": 0.80, "passed": True, "reason": "ok"}},
    )
    policy = RegressionPolicy(
        experiment_id=uuid4(),
        metric_name="llm_judge",
        max_allowed_drop=0.05,
    )
    outcome = RegressionService().evaluate(
        current_run=current,
        baseline_run=baseline,
        current_results=[current_cr],
        baseline_results=[baseline_cr],
        policies=[policy],
        current_scores_by_case={tid: current_cr.metric_scores},
        baseline_scores_by_case={tid: baseline_cr.metric_scores},
    )
    assert outcome.status.value == "FAIL"
    assert outcome.aggregate["llm_judge"].delta == pytest.approx(-0.14)
