import assert from "node:assert/strict";
import test from "node:test";

import {
  buildCaseComparisons,
  buildMetricComparisons,
  deltaArrow,
  extractMetricScore,
  summarizeMetricComparisons,
} from "./compare.ts";
import type { CaseResult, EvaluationRun, RegressionInfo } from "../types/api.ts";

function run(partial: Partial<EvaluationRun> & { id: string }): EvaluationRun {
  return {
    run_id: partial.id,
    project_id: "p1",
    experiment_id: "e1",
    is_baseline: false,
    dataset_version_id: "dv1",
    dataset_version: null,
    status: "COMPLETED",
    config_snapshot: {},
    error_message: null,
    started_at: null,
    finished_at: null,
    created_at: "2026-01-01T00:00:00Z",
    total_cases: 1,
    completed_cases: 1,
    failed_cases: 0,
    pending_cases: 0,
    regression_status: "NOT_EVALUATED",
    baseline_run_id: "b1",
    regression: null,
    metric_aggregates: {},
    ...partial,
  };
}

function caseResult(
  testCaseId: string,
  scores: Record<string, number>,
  extras: Partial<CaseResult> = {},
): CaseResult {
  return {
    id: `cr-${testCaseId}`,
    run_id: "r",
    test_case_id: testCaseId,
    external_id: testCaseId,
    actual_output: { answer: "x" },
    status: "COMPLETED",
    metric_scores: Object.fromEntries(
      Object.entries(scores).map(([k, v]) => [k, { score: v, passed: true }]),
    ),
    is_regression: false,
    error_message: null,
    created_at: "2026-01-01T00:00:00Z",
    ...extras,
  };
}

test("extractMetricScore reads nested score", () => {
  assert.equal(extractMetricScore({ string_similarity: { score: 0.86 } }, "string_similarity"), 0.86);
});

test("delta is current - baseline from regression aggregate", () => {
  const current = run({
    id: "c1",
    metric_aggregates: { string_similarity: { average: 0.86 } },
  });
  const baseline = run({
    id: "b1",
    metric_aggregates: { string_similarity: { average: 0.94 } },
  });
  const regression: RegressionInfo = {
    status: "FAIL",
    baseline_run_id: "b1",
    regressed_case_count: 1,
    aggregate: {
      string_similarity: {
        baseline: 0.94,
        current: 0.86,
        delta: -0.08,
        threshold: 0.05,
        violated: true,
        reasons: ["drop"],
      },
    },
    regressed_cases: [],
    violations: [],
    incomparable_cases: [],
    notes: [],
  };

  const rows = buildMetricComparisons(current, baseline, regression);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].delta, -0.08);
  assert.equal(rows[0].status, "REGRESSED");
  assert.equal(rows[0].threshold, 0.05);
});

test("improved metric within aggregates without inventing threshold", () => {
  const current = run({
    id: "c1",
    metric_aggregates: { exact_match: { average: 0.93 } },
  });
  const baseline = run({
    id: "b1",
    metric_aggregates: { exact_match: { average: 0.9 } },
  });
  const rows = buildMetricComparisons(current, baseline, null);
  assert.equal(rows[0].status, "IMPROVED");
  assert.equal(rows[0].threshold, null);
  assert.ok(Math.abs((rows[0].delta ?? 0) - 0.03) < 1e-9);
});

test("summary counts improved and degraded", () => {
  const summary = summarizeMetricComparisons(
    [
      {
        metric: "a",
        baseline: 0.9,
        current: 0.95,
        delta: 0.05,
        threshold: 0.05,
        status: "IMPROVED",
        violated: false,
        reasons: [],
      },
      {
        metric: "b",
        baseline: 0.94,
        current: 0.86,
        delta: -0.08,
        threshold: 0.05,
        status: "REGRESSED",
        violated: true,
        reasons: [],
      },
    ],
    "FAIL",
  );
  assert.equal(summary.metricsEvaluated, 2);
  assert.equal(summary.metricsImproved, 1);
  assert.equal(summary.metricsDegraded, 1);
  assert.equal(summary.regressionStatus, "FAIL");
});

test("missing case is NOT_COMPARABLE", () => {
  const rows = buildCaseComparisons(
    [caseResult("only-current", { string_similarity: 0.9 })],
    [caseResult("only-baseline", { string_similarity: 0.9 })],
    null,
  );
  assert.equal(rows.length, 2);
  assert.ok(rows.every((r) => r.status === "NOT_COMPARABLE"));
});

test("regressed case uses backend reason", () => {
  const rows = buildCaseComparisons(
    [caseResult("t1", { string_similarity: 0.7 })],
    [caseResult("t1", { string_similarity: 0.95 })],
    {
      status: "FAIL",
      baseline_run_id: "b1",
      regressed_case_count: 1,
      aggregate: {},
      regressed_cases: [
        {
          test_case_id: "t1",
          metric: "string_similarity",
          baseline_score: 0.95,
          current_score: 0.7,
          delta: -0.25,
          reason: "metric_drop_exceeded_threshold",
        },
      ],
      violations: [],
      incomparable_cases: [],
      notes: [],
    },
  );
  assert.equal(rows[0].status, "REGRESSED");
  assert.equal(rows[0].reason, "metric_drop_exceeded_threshold");
});

test("delta arrows", () => {
  assert.equal(deltaArrow(0.01), "↑");
  assert.equal(deltaArrow(-0.01), "↓");
  assert.equal(deltaArrow(0), "→");
  assert.equal(deltaArrow(null), "→");
});
