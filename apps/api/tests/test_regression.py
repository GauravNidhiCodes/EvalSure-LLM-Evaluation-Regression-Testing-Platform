from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.models import CaseResult, CaseResultStatus, EvaluationRun, RegressionPolicy, RunStatus
from app.regression.engine import RegressionService

SAMPLE_CASES = [
    {
        "external_id": "r1",
        "input": {"question": "What is normalization?"},
        "expected": {"answer": "Normalization organizes data to reduce redundancy"},
        "metadata": {},
        "tags": [],
    },
    {
        "external_id": "r2",
        "input": {"question": "What is a primary key?"},
        "expected": {"answer": "A unique identifier for a table row"},
        "metadata": {},
        "tags": [],
    },
]


async def _fixture(client: AsyncClient) -> dict:
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": f"reg-{uuid4().hex[:8]}@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
    project = await client.post("/api/v1/projects", headers=headers, json={"name": "Reg"})
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
    exp = await client.post(
        f"/api/v1/projects/{project_id}/experiments",
        headers=headers,
        json={"name": "Customer Support RAG"},
    )
    return {
        "headers": headers,
        "project_id": project_id,
        "version_id": version.json()["id"],
        "case_map": case_map,
        "experiment_id": exp.json()["id"],
    }


async def _complete_run(
    client: AsyncClient,
    ctx: dict,
    outputs: dict[str, dict],
) -> str:
    created = await client.post(
        f"/api/v1/projects/{ctx['project_id']}/runs",
        headers=ctx["headers"],
        json={
            "experiment_id": ctx["experiment_id"],
            "dataset_version_id": ctx["version_id"],
            "metrics": ["string_similarity", "exact_match"],
        },
    )
    run_id = created.json()["id"]
    results = [
        {"test_case_id": ctx["case_map"][eid], "actual_output": out}
        for eid, out in outputs.items()
    ]
    submit = await client.post(
        f"/api/v1/runs/{run_id}/results",
        headers=ctx["headers"],
        json={"results": results},
    )
    assert submit.json()["run"]["status"] == "COMPLETED"
    return run_id


GOOD = {
    "r1": {"answer": "Normalization organizes data to reduce redundancy"},
    "r2": {"answer": "A unique identifier for a table row"},
}
BAD = {
    "r1": {"answer": "cats"},
    "r2": {"answer": "dogs"},
}
SLIGHTLY_WORSE = {
    "r1": {"answer": "Normalization organizes data to reduce redundancy somewhat"},
    "r2": {"answer": "A unique identifier for a table row roughly"},
}


@pytest.mark.asyncio
async def test_policy_create_update_and_list(client: AsyncClient) -> None:
    ctx = await _fixture(client)
    created = await client.post(
        f"/api/v1/experiments/{ctx['experiment_id']}/regression-policies",
        headers=ctx["headers"],
        json={
            "metric_name": "string_similarity",
            "max_allowed_drop": 0.05,
            "min_aggregate_score": 0.80,
            "max_regressed_cases": 2,
        },
    )
    assert created.status_code == 201
    policy_id = created.json()["id"]

    updated = await client.post(
        f"/api/v1/experiments/{ctx['experiment_id']}/regression-policies",
        headers=ctx["headers"],
        json={
            "metric_name": "string_similarity",
            "max_allowed_drop": 0.10,
            "min_aggregate_score": 0.70,
            "max_regressed_cases": 1,
        },
    )
    assert updated.status_code == 201
    assert updated.json()["id"] == policy_id
    assert updated.json()["max_allowed_drop"] == 0.10

    listed = await client.get(
        f"/api/v1/experiments/{ctx['experiment_id']}/regression-policies",
        headers=ctx["headers"],
    )
    assert len(listed.json()) == 1


@pytest.mark.asyncio
async def test_invalid_metric_and_threshold(client: AsyncClient) -> None:
    ctx = await _fixture(client)
    bad_metric = await client.post(
        f"/api/v1/experiments/{ctx['experiment_id']}/regression-policies",
        headers=ctx["headers"],
        json={"metric_name": "not_a_real_metric", "max_allowed_drop": 0.05},
    )
    assert bad_metric.status_code == 422

    bad_drop = await client.post(
        f"/api/v1/experiments/{ctx['experiment_id']}/regression-policies",
        headers=ctx["headers"],
        json={"metric_name": "exact_match", "max_allowed_drop": 1.5},
    )
    assert bad_drop.status_code == 422


@pytest.mark.asyncio
async def test_no_baseline_or_policy_not_evaluated(client: AsyncClient) -> None:
    ctx = await _fixture(client)
    run_id = await _complete_run(client, ctx, GOOD)
    result = await client.post(
        f"/api/v1/runs/{run_id}/evaluate-regression",
        headers=ctx["headers"],
    )
    assert result.status_code == 200
    assert result.json()["regression"]["status"] == "NOT_EVALUATED"
    assert result.json()["evaluation_status"] == "COMPLETED"

    await client.post(
        f"/api/v1/experiments/{ctx['experiment_id']}/baseline/{run_id}",
        headers=ctx["headers"],
    )
    still = await client.post(
        f"/api/v1/runs/{run_id}/evaluate-regression",
        headers=ctx["headers"],
    )
    assert still.json()["regression"]["status"] == "NOT_EVALUATED"


@pytest.mark.asyncio
async def test_aggregate_pass_and_fail(client: AsyncClient) -> None:
    ctx = await _fixture(client)
    baseline_id = await _complete_run(client, ctx, GOOD)
    await client.post(
        f"/api/v1/experiments/{ctx['experiment_id']}/baseline/{baseline_id}",
        headers=ctx["headers"],
    )
    await client.post(
        f"/api/v1/experiments/{ctx['experiment_id']}/regression-policies",
        headers=ctx["headers"],
        json={
            "metric_name": "string_similarity",
            "max_allowed_drop": 0.05,
            "min_aggregate_score": 0.80,
            "max_regressed_cases": 10,
        },
    )

    # Same quality → PASS
    good_run = await _complete_run(client, ctx, GOOD)
    pass_res = await client.post(
        f"/api/v1/runs/{good_run}/evaluate-regression",
        headers=ctx["headers"],
    )
    assert pass_res.json()["regression"]["status"] == "PASS"
    assert pass_res.json()["evaluation_status"] == "COMPLETED"

    # Large drop → FAIL
    bad_run = await _complete_run(client, ctx, BAD)
    fail_res = await client.post(
        f"/api/v1/runs/{bad_run}/evaluate-regression",
        headers=ctx["headers"],
    )
    body = fail_res.json()
    assert body["evaluation_status"] == "COMPLETED"
    assert body["regression"]["status"] == "FAIL"
    assert body["regression"]["regressed_case_count"] >= 1
    assert body["regression"]["aggregate"]["string_similarity"]["violated"] is True

    detail = await client.get(f"/api/v1/runs/{bad_run}", headers=ctx["headers"])
    assert detail.json()["status"] == "COMPLETED"
    assert detail.json()["regression_status"] == "FAIL"
    assert detail.json()["regression"]["status"] == "FAIL"

    cases = await client.get(f"/api/v1/runs/{bad_run}/results", headers=ctx["headers"])
    assert any(c["is_regression"] for c in cases.json())

    baseline_cases = await client.get(
        f"/api/v1/runs/{baseline_id}/results", headers=ctx["headers"]
    )
    assert all(c["is_regression"] is False for c in baseline_cases.json())


@pytest.mark.asyncio
async def test_idempotent_evaluation(client: AsyncClient) -> None:
    ctx = await _fixture(client)
    baseline_id = await _complete_run(client, ctx, GOOD)
    await client.post(
        f"/api/v1/experiments/{ctx['experiment_id']}/baseline/{baseline_id}",
        headers=ctx["headers"],
    )
    await client.post(
        f"/api/v1/experiments/{ctx['experiment_id']}/regression-policies",
        headers=ctx["headers"],
        json={"metric_name": "string_similarity", "max_allowed_drop": 0.05},
    )
    run_id = await _complete_run(client, ctx, BAD)
    first = await client.post(f"/api/v1/runs/{run_id}/evaluate-regression", headers=ctx["headers"])
    second = await client.post(f"/api/v1/runs/{run_id}/evaluate-regression", headers=ctx["headers"])
    assert first.json()["regression"]["status"] == second.json()["regression"]["status"]
    assert (
        first.json()["regression"]["regressed_case_count"]
        == second.json()["regression"]["regressed_case_count"]
    )


@pytest.mark.asyncio
async def test_delete_policy(client: AsyncClient) -> None:
    ctx = await _fixture(client)
    created = await client.post(
        f"/api/v1/experiments/{ctx['experiment_id']}/regression-policies",
        headers=ctx["headers"],
        json={"metric_name": "exact_match", "max_allowed_drop": 0.0},
    )
    policy_id = created.json()["id"]
    deleted = await client.delete(
        f"/api/v1/regression-policies/{policy_id}",
        headers=ctx["headers"],
    )
    assert deleted.status_code == 204
    listed = await client.get(
        f"/api/v1/experiments/{ctx['experiment_id']}/regression-policies",
        headers=ctx["headers"],
    )
    assert listed.json() == []


@pytest.mark.asyncio
async def test_min_aggregate_score_violation(client: AsyncClient) -> None:
    ctx = await _fixture(client)
    baseline_id = await _complete_run(client, ctx, GOOD)
    await client.post(
        f"/api/v1/experiments/{ctx['experiment_id']}/baseline/{baseline_id}",
        headers=ctx["headers"],
    )
    await client.post(
        f"/api/v1/experiments/{ctx['experiment_id']}/regression-policies",
        headers=ctx["headers"],
        json={
            "metric_name": "string_similarity",
            "max_allowed_drop": 1.0,
            "min_aggregate_score": 0.95,
        },
    )
    run_id = await _complete_run(client, ctx, SLIGHTLY_WORSE)
    result = await client.post(
        f"/api/v1/runs/{run_id}/evaluate-regression",
        headers=ctx["headers"],
    )
    assert result.json()["regression"]["status"] == "FAIL"
    reasons = result.json()["regression"]["aggregate"]["string_similarity"]["reasons"]
    assert any("min_aggregate_score" in r for r in reasons)


def test_regression_service_unit_threshold() -> None:
    engine = RegressionService()
    tid = uuid4()
    baseline_run = EvaluationRun(
        id=uuid4(),
        project_id=uuid4(),
        dataset_version_id=uuid4(),
        status=RunStatus.COMPLETED.value,
    )
    current_run = EvaluationRun(
        id=uuid4(),
        project_id=baseline_run.project_id,
        dataset_version_id=baseline_run.dataset_version_id,
        status=RunStatus.COMPLETED.value,
    )
    baseline_cr = CaseResult(
        id=uuid4(),
        run_id=baseline_run.id,
        test_case_id=tid,
        status=CaseResultStatus.COMPLETED.value,
        metric_scores={"string_similarity": {"score": 0.94, "passed": True}},
    )
    current_cr = CaseResult(
        id=uuid4(),
        run_id=current_run.id,
        test_case_id=tid,
        status=CaseResultStatus.COMPLETED.value,
        metric_scores={"string_similarity": {"score": 0.86, "passed": True}},
    )
    policy = RegressionPolicy(
        id=uuid4(),
        experiment_id=uuid4(),
        metric_name="string_similarity",
        max_allowed_drop=0.05,
    )
    outcome = engine.evaluate(
        current_run=current_run,
        baseline_run=baseline_run,
        current_results=[current_cr],
        baseline_results=[baseline_cr],
        policies=[policy],
        current_scores_by_case={tid: current_cr.metric_scores},
        baseline_scores_by_case={tid: baseline_cr.metric_scores},
    )
    assert outcome.status.value == "FAIL"
    assert outcome.aggregate["string_similarity"].delta == pytest.approx(-0.08)
    assert outcome.aggregate["string_similarity"].violated is True
    assert outcome.regressed_case_count == 1


def _engine_pair(
    *,
    baseline_score: float,
    current_score: float,
    baseline_status: str = CaseResultStatus.COMPLETED.value,
    current_status: str = CaseResultStatus.COMPLETED.value,
    max_allowed_drop: float = 0.05,
    extra_baseline: CaseResult | None = None,
    extra_current: CaseResult | None = None,
    baseline_scores_extra: dict | None = None,
    current_scores_extra: dict | None = None,
):
    engine = RegressionService()
    tid = uuid4()
    baseline_run = EvaluationRun(
        id=uuid4(),
        project_id=uuid4(),
        dataset_version_id=uuid4(),
        status=RunStatus.COMPLETED.value,
    )
    current_run = EvaluationRun(
        id=uuid4(),
        project_id=baseline_run.project_id,
        dataset_version_id=baseline_run.dataset_version_id,
        status=RunStatus.COMPLETED.value,
    )
    baseline_cr = CaseResult(
        id=uuid4(),
        run_id=baseline_run.id,
        test_case_id=tid,
        status=baseline_status,
        metric_scores={"string_similarity": {"score": baseline_score, "passed": True}},
    )
    current_cr = CaseResult(
        id=uuid4(),
        run_id=current_run.id,
        test_case_id=tid,
        status=current_status,
        metric_scores={"string_similarity": {"score": current_score, "passed": current_status == CaseResultStatus.COMPLETED.value}},
    )
    policy = RegressionPolicy(
        id=uuid4(),
        experiment_id=uuid4(),
        metric_name="string_similarity",
        max_allowed_drop=max_allowed_drop,
    )
    baseline_results = [baseline_cr] + ([extra_baseline] if extra_baseline else [])
    current_results = [current_cr] + ([extra_current] if extra_current else [])
    baseline_scores = {tid: baseline_cr.metric_scores}
    current_scores = {tid: current_cr.metric_scores}
    if baseline_scores_extra:
        baseline_scores.update(baseline_scores_extra)
    if current_scores_extra:
        current_scores.update(current_scores_extra)
    outcome = engine.evaluate(
        current_run=current_run,
        baseline_run=baseline_run,
        current_results=current_results,
        baseline_results=baseline_results,
        policies=[policy],
        current_scores_by_case=current_scores,
        baseline_scores_by_case=baseline_scores,
    )
    return outcome, tid


def test_drop_within_threshold_passes() -> None:
    outcome, _ = _engine_pair(baseline_score=0.94, current_score=0.90, max_allowed_drop=0.05)
    assert outcome.status.value == "PASS"
    assert outcome.aggregate["string_similarity"].violated is False
    assert outcome.regressed_case_count == 0


def test_improved_case_not_regressed() -> None:
    outcome, _ = _engine_pair(baseline_score=0.70, current_score=0.95, max_allowed_drop=0.05)
    assert outcome.status.value == "PASS"
    assert outcome.regressed_case_count == 0


def test_baseline_passed_current_failed() -> None:
    outcome, tid = _engine_pair(
        baseline_score=0.95,
        current_score=0.10,
        current_status=CaseResultStatus.FAILED.value,
        max_allowed_drop=1.0,
    )
    assert outcome.regressed_case_count == 1
    assert any(
        c.test_case_id == str(tid) and "baseline_passed_current_failed" in c.reason
        for c in outcome.regressed_cases
    )


def test_missing_cases_are_incomparable_not_crash() -> None:
    engine = RegressionService()
    shared = uuid4()
    only_base = uuid4()
    only_cur = uuid4()
    baseline_run = EvaluationRun(
        id=uuid4(), project_id=uuid4(), dataset_version_id=uuid4(), status=RunStatus.COMPLETED.value
    )
    current_run = EvaluationRun(
        id=uuid4(),
        project_id=baseline_run.project_id,
        dataset_version_id=baseline_run.dataset_version_id,
        status=RunStatus.COMPLETED.value,
    )
    policy = RegressionPolicy(
        id=uuid4(),
        experiment_id=uuid4(),
        metric_name="string_similarity",
        max_allowed_drop=0.05,
    )
    baseline_results = [
        CaseResult(
            id=uuid4(),
            run_id=baseline_run.id,
            test_case_id=shared,
            status=CaseResultStatus.COMPLETED.value,
            metric_scores={"string_similarity": {"score": 1.0, "passed": True}},
        ),
        CaseResult(
            id=uuid4(),
            run_id=baseline_run.id,
            test_case_id=only_base,
            status=CaseResultStatus.COMPLETED.value,
            metric_scores={"string_similarity": {"score": 1.0, "passed": True}},
        ),
    ]
    current_results = [
        CaseResult(
            id=uuid4(),
            run_id=current_run.id,
            test_case_id=shared,
            status=CaseResultStatus.COMPLETED.value,
            metric_scores={"string_similarity": {"score": 1.0, "passed": True}},
        ),
        CaseResult(
            id=uuid4(),
            run_id=current_run.id,
            test_case_id=only_cur,
            status=CaseResultStatus.COMPLETED.value,
            metric_scores={"string_similarity": {"score": 1.0, "passed": True}},
        ),
    ]
    outcome = engine.evaluate(
        current_run=current_run,
        baseline_run=baseline_run,
        current_results=current_results,
        baseline_results=baseline_results,
        policies=[policy],
        current_scores_by_case={
            shared: current_results[0].metric_scores,
            only_cur: current_results[1].metric_scores,
        },
        baseline_scores_by_case={
            shared: baseline_results[0].metric_scores,
            only_base: baseline_results[1].metric_scores,
        },
    )
    assert outcome.status.value == "PASS"
    reasons = {item["reason"] for item in outcome.incomparable_cases}
    assert "missing_in_current" in reasons
    assert "missing_in_baseline" in reasons


@pytest.mark.asyncio
async def test_unauthorized_experiment_policy_access(client: AsyncClient) -> None:
    ctx = await _fixture(client)
    other = await client.post(
        "/api/v1/auth/register",
        json={"email": f"other-{uuid4().hex[:8]}@example.com", "password": "password123"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    forbidden = await client.post(
        f"/api/v1/experiments/{ctx['experiment_id']}/regression-policies",
        headers=other_headers,
        json={"metric_name": "exact_match", "max_allowed_drop": 0.1},
    )
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_drop_within_threshold_api(client: AsyncClient) -> None:
    ctx = await _fixture(client)
    baseline_id = await _complete_run(client, ctx, GOOD)
    await client.post(
        f"/api/v1/experiments/{ctx['experiment_id']}/baseline/{baseline_id}",
        headers=ctx["headers"],
    )
    await client.post(
        f"/api/v1/experiments/{ctx['experiment_id']}/regression-policies",
        headers=ctx["headers"],
        json={"metric_name": "string_similarity", "max_allowed_drop": 0.50},
    )
    # Mild wording change should stay within a generous threshold
    mild = {
        "r1": {"answer": "Normalization organizes data to reduce redundancy"},
        "r2": {"answer": "A unique identifier for a table row"},
    }
    run_id = await _complete_run(client, ctx, mild)
    result = await client.post(
        f"/api/v1/runs/{run_id}/evaluate-regression",
        headers=ctx["headers"],
    )
    assert result.json()["regression"]["status"] == "PASS"
