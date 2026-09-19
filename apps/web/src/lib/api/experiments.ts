import { apiFetch, unwrapPage, type Page } from "@/lib/api/client";
import type { EvaluationRun, Experiment, RegressionPolicy } from "@/types/api";

export async function listExperiments(projectId: string): Promise<Experiment[]> {
  const page = await apiFetch<Page<Experiment>>(
    `/projects/${projectId}/experiments?page_size=200`,
  );
  return unwrapPage(page);
}

export async function getExperiment(experimentId: string): Promise<Experiment> {
  return apiFetch<Experiment>(`/experiments/${experimentId}`);
}

export async function listExperimentRuns(experimentId: string): Promise<EvaluationRun[]> {
  const page = await apiFetch<Page<EvaluationRun>>(
    `/experiments/${experimentId}/runs?page_size=200`,
  );
  return unwrapPage(page);
}

export async function listRegressionPolicies(
  experimentId: string,
): Promise<RegressionPolicy[]> {
  return apiFetch<RegressionPolicy[]>(`/experiments/${experimentId}/regression-policies`);
}

/** Aggregate runs across all experiments in a project (no dedicated project runs API). */
export async function listProjectRuns(projectId: string): Promise<EvaluationRun[]> {
  const experiments = await listExperiments(projectId);
  const batches = await Promise.all(
    experiments.map((exp) => listExperimentRuns(exp.id).catch(() => [] as EvaluationRun[])),
  );
  const runs = batches.flat();
  runs.sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  return runs;
}
