/** Pure comparison helpers — display-only; regression truth comes from the API. */

import type {
  CaseResult,
  EvaluationRun,
  MetricAggregate,
  RegressedCase,
  RegressionInfo,
} from "@/types/api";

export type MetricCompareStatus = "REGRESSED" | "IMPROVED" | "WITHIN_LIMIT" | "DEGRADED" | "UNCHANGED" | "UNKNOWN";

export type CaseCompareStatus =
  | "IMPROVED"
  | "UNCHANGED"
  | "DEGRADED"
  | "REGRESSED"
  | "NOT_COMPARABLE";

export interface MetricComparisonRow {
  metric: string;
  baseline: number | null;
  current: number | null;
  delta: number | null;
  threshold: number | null;
  status: MetricCompareStatus;
  violated: boolean;
  reasons: string[];
}

export interface CaseComparisonRow {
  test_case_id: string;
  external_id: string | null;
  metric: string | null;
  baseline_score: number | null;
  current_score: number | null;
  delta: number | null;
  status: CaseCompareStatus;
  reason: string | null;
  current_result: CaseResult | null;
  baseline_result: CaseResult | null;
}

export interface ComparisonSummary {
  metricsEvaluated: number;
  metricsImproved: number;
  metricsDegraded: number;
  regressionStatus: string;
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

export function extractMetricScore(
  metricScores: Record<string, unknown> | null | undefined,
  metric: string,
): number | null {
  if (!metricScores || !(metric in metricScores)) return null;
  const entry = metricScores[metric];
  if (typeof entry === "object" && entry !== null && "score" in entry) {
    return asNumber((entry as { score: unknown }).score);
  }
  return asNumber(entry);
}

export function averageFromAggregate(agg: MetricAggregate | undefined): number | null {
  if (!agg) return null;
  return asNumber(agg.average);
}

/**
 * Build metric rows preferring backend regression.aggregate when present.
 * Falls back to metric_aggregates averages for display only (no invented thresholds).
 */
export function buildMetricComparisons(
  current: EvaluationRun,
  baseline: EvaluationRun,
  regression: RegressionInfo | null | undefined,
): MetricComparisonRow[] {
  const rows = new Map<string, MetricComparisonRow>();

  const aggregate = regression?.aggregate ?? {};
  for (const [metric, data] of Object.entries(aggregate)) {
    const baselineScore = asNumber(data.baseline);
    const currentScore = asNumber(data.current);
    const delta =
      asNumber(data.delta) ??
      (baselineScore !== null && currentScore !== null ? currentScore - baselineScore : null);
    const threshold = asNumber(data.threshold);
    const violated = Boolean(data.violated);
    const reasons = Array.isArray(data.reasons)
      ? data.reasons.map((r) => String(r))
      : [];

    let status: MetricCompareStatus = "UNKNOWN";
    if (violated) {
      status = "REGRESSED";
    } else if (delta !== null) {
      if (delta > 1e-9) status = "IMPROVED";
      else if (delta < -1e-9) status = "WITHIN_LIMIT";
      else status = "UNCHANGED";
    }

    rows.set(metric, {
      metric,
      baseline: baselineScore,
      current: currentScore,
      delta,
      threshold,
      status,
      violated,
      reasons,
    });
  }

  const metricNames = new Set([
    ...Object.keys(current.metric_aggregates || {}),
    ...Object.keys(baseline.metric_aggregates || {}),
  ]);

  for (const metric of metricNames) {
    if (rows.has(metric)) continue;
    const baselineScore = averageFromAggregate(baseline.metric_aggregates?.[metric]);
    const currentScore = averageFromAggregate(current.metric_aggregates?.[metric]);
    const delta =
      baselineScore !== null && currentScore !== null ? currentScore - baselineScore : null;
    let status: MetricCompareStatus = "UNKNOWN";
    if (delta !== null) {
      if (delta > 1e-9) status = "IMPROVED";
      else if (delta < -1e-9) status = "DEGRADED";
      else status = "UNCHANGED";
    }
    rows.set(metric, {
      metric,
      baseline: baselineScore,
      current: currentScore,
      delta,
      threshold: null,
      status,
      violated: false,
      reasons: [],
    });
  }

  return Array.from(rows.values()).sort((a, b) => a.metric.localeCompare(b.metric));
}

export function summarizeMetricComparisons(
  rows: MetricComparisonRow[],
  regressionStatus: string,
): ComparisonSummary {
  return {
    metricsEvaluated: rows.length,
    metricsImproved: rows.filter((r) => r.status === "IMPROVED").length,
    metricsDegraded: rows.filter(
      (r) => r.status === "DEGRADED" || r.status === "REGRESSED" || r.status === "WITHIN_LIMIT",
    ).length,
    regressionStatus,
  };
}

export function buildCaseComparisons(
  currentResults: CaseResult[],
  baselineResults: CaseResult[],
  regression: RegressionInfo | null | undefined,
  preferredMetrics: string[] = [],
): CaseComparisonRow[] {
  const currentByCase = new Map(currentResults.map((r) => [r.test_case_id, r]));
  const baselineByCase = new Map(baselineResults.map((r) => [r.test_case_id, r]));
  const allIds = new Set([...currentByCase.keys(), ...baselineByCase.keys()]);

  const regressedByCase = new Map<string, RegressedCase>();
  for (const item of regression?.regressed_cases ?? []) {
    regressedByCase.set(item.test_case_id, item);
  }

  const rows: CaseComparisonRow[] = [];
  for (const testCaseId of allIds) {
    const current = currentByCase.get(testCaseId) ?? null;
    const baseline = baselineByCase.get(testCaseId) ?? null;
    const regressed = regressedByCase.get(testCaseId);

    if (!current || !baseline) {
      rows.push({
        test_case_id: testCaseId,
        external_id: current?.external_id ?? baseline?.external_id ?? null,
        metric: regressed?.metric ?? null,
        baseline_score: regressed?.baseline_score ?? null,
        current_score: regressed?.current_score ?? null,
        delta: regressed?.delta ?? null,
        status: "NOT_COMPARABLE",
        reason: !current ? "missing_in_current" : "missing_in_baseline",
        current_result: current,
        baseline_result: baseline,
      });
      continue;
    }

    if (regressed) {
      rows.push({
        test_case_id: testCaseId,
        external_id: current.external_id,
        metric: regressed.metric,
        baseline_score: regressed.baseline_score,
        current_score: regressed.current_score,
        delta: regressed.delta,
        status: "REGRESSED",
        reason: regressed.reason,
        current_result: current,
        baseline_result: baseline,
      });
      continue;
    }

    const metric =
      preferredMetrics.find(
        (m) =>
          extractMetricScore(current.metric_scores, m) !== null &&
          extractMetricScore(baseline.metric_scores, m) !== null,
      ) ??
      Object.keys(current.metric_scores || {}).find(
        (m) => extractMetricScore(baseline.metric_scores, m) !== null,
      ) ??
      null;

    if (!metric) {
      rows.push({
        test_case_id: testCaseId,
        external_id: current.external_id,
        metric: null,
        baseline_score: null,
        current_score: null,
        delta: null,
        status: "NOT_COMPARABLE",
        reason: "missing_metric_score",
        current_result: current,
        baseline_result: baseline,
      });
      continue;
    }

    const baselineScore = extractMetricScore(baseline.metric_scores, metric);
    const currentScore = extractMetricScore(current.metric_scores, metric);
    const delta =
      baselineScore !== null && currentScore !== null ? currentScore - baselineScore : null;

    let status: CaseCompareStatus = "UNCHANGED";
    if (delta === null) status = "NOT_COMPARABLE";
    else if (delta > 1e-9) status = "IMPROVED";
    else if (delta < -1e-9) status = "DEGRADED";

    rows.push({
      test_case_id: testCaseId,
      external_id: current.external_id,
      metric,
      baseline_score: baselineScore,
      current_score: currentScore,
      delta,
      status,
      reason: null,
      current_result: current,
      baseline_result: baseline,
    });
  }

  return rows.sort((a, b) => (a.external_id || a.test_case_id).localeCompare(b.external_id || b.test_case_id));
}

export function deltaArrow(delta: number | null): string {
  if (delta === null) return "→";
  if (delta > 1e-9) return "↑";
  if (delta < -1e-9) return "↓";
  return "→";
}

export function metricStatusLabel(status: MetricCompareStatus): string {
  switch (status) {
    case "REGRESSED":
      return "REGRESSED";
    case "IMPROVED":
      return "IMPROVED";
    case "WITHIN_LIMIT":
      return "WITHIN LIMIT";
    case "DEGRADED":
      return "DEGRADED";
    case "UNCHANGED":
      return "UNCHANGED";
    default:
      return "UNKNOWN";
  }
}
