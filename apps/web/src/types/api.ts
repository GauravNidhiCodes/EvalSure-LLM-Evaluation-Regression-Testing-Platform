/** Types matching EVALSURE FastAPI response schemas. */

export type RunStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
export type CaseResultStatus = "PENDING" | "COMPLETED" | "FAILED";
export type RegressionStatus = "NOT_EVALUATED" | "PASS" | "FAIL";

export interface Project {
  id: string;
  name: string;
  description: string | null;
  owner_id: string;
  created_at: string;
}

export interface Dataset {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface DatasetVersion {
  id: string;
  dataset_id: string;
  version: number;
  content_hash: string;
  created_at: string;
  test_case_count: number | null;
}

export interface TestCase {
  id: string;
  external_id: string;
  input: Record<string, unknown>;
  expected: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
  tags: string[];
}

export interface Experiment {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  baseline_run_id: string | null;
  created_at: string;
}

export interface DatasetVersionSummary {
  id: string;
  dataset_id: string;
  version: number;
  content_hash: string;
}

export interface MetricAggregate {
  average?: number;
  minimum?: number;
  maximum?: number;
  count?: number;
  [key: string]: unknown;
}

export interface RegressionAggregateEntry {
  baseline?: number | null;
  current?: number | null;
  delta?: number | null;
  threshold?: number | null;
  min_aggregate_score?: number | null;
  violated?: boolean;
  reasons?: string[];
  [key: string]: unknown;
}

export interface RegressionInfo {
  status: RegressionStatus;
  baseline_run_id: string | null;
  regressed_case_count: number;
  aggregate: Record<string, RegressionAggregateEntry>;
  regressed_cases: RegressedCase[];
  violations: Array<Record<string, unknown>>;
  incomparable_cases: Array<Record<string, unknown>>;
  notes: string[];
}

export interface RegressedCase {
  test_case_id: string;
  metric: string;
  baseline_score: number;
  current_score: number;
  delta: number;
  reason: string;
}

export interface EvaluationRun {
  id: string;
  run_id: string;
  project_id: string;
  experiment_id: string | null;
  is_baseline: boolean;
  dataset_version_id: string;
  dataset_version: DatasetVersionSummary | null;
  status: RunStatus;
  config_snapshot: Record<string, unknown>;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  total_cases: number;
  completed_cases: number;
  failed_cases: number;
  pending_cases: number;
  regression_status: RegressionStatus;
  baseline_run_id: string | null;
  regression: RegressionInfo | null;
  metric_aggregates: Record<string, MetricAggregate>;
}

export interface CaseResult {
  id: string;
  run_id: string;
  test_case_id: string;
  external_id: string | null;
  actual_output: Record<string, unknown> | null;
  status: CaseResultStatus;
  metric_scores: Record<string, unknown>;
  is_regression: boolean;
  error_message: string | null;
  created_at: string;
}

export interface RegressionPolicy {
  id: string;
  experiment_id: string;
  metric_name: string;
  max_allowed_drop: number;
  min_aggregate_score: number | null;
  max_regressed_cases: number | null;
  created_at: string;
}

export interface ApiKeyMeta {
  id: string;
  name: string;
  key_prefix: string;
  created_at: string;
  revoked_at: string | null;
  status: "active" | "revoked";
}

export interface ApiKeyCreated {
  id: string;
  name: string;
  key_prefix: string;
  api_key: string;
  created_at: string;
}

export interface TraceEvent {
  id: string;
  run_id: string;
  case_result_id: string | null;
  event_type: string;
  timestamp: string;
  data: Record<string, unknown>;
  created_at: string;
}

export interface RunTraces {
  run_id: string;
  events: TraceEvent[];
}

export interface CaseTraces {
  run_id: string;
  case_result_id: string;
  events: TraceEvent[];
}
