import { apiFetch } from "@/lib/api/client";
import type { CaseTraces, RunTraces } from "@/types/api";

export async function getRunTraces(runId: string): Promise<RunTraces> {
  return apiFetch<RunTraces>(`/runs/${runId}/traces`);
}

export async function getCaseTraces(
  runId: string,
  caseResultId: string,
): Promise<CaseTraces> {
  return apiFetch<CaseTraces>(`/runs/${runId}/cases/${caseResultId}/traces`);
}
