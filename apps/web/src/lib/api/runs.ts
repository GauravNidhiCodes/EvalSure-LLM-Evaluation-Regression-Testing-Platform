import { apiFetch } from "@/lib/api/client";
import type { CaseResult, EvaluationRun } from "@/types/api";

export async function getRun(runId: string): Promise<EvaluationRun> {
  return apiFetch<EvaluationRun>(`/runs/${runId}`);
}

export async function listCaseResults(runId: string): Promise<CaseResult[]> {
  return apiFetch<CaseResult[]>(`/runs/${runId}/results`);
}

export async function listMetrics(): Promise<string[]> {
  return apiFetch<string[]>("/metrics");
}
