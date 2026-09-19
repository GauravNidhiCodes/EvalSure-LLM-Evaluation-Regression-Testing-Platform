import { apiFetch } from "@/lib/api/client";
import type { Dataset, DatasetVersion, TestCase } from "@/types/api";

export async function listDatasets(projectId: string): Promise<Dataset[]> {
  return apiFetch<Dataset[]>(`/projects/${projectId}/datasets`);
}

export async function getDataset(datasetId: string): Promise<Dataset> {
  return apiFetch<Dataset>(`/datasets/${datasetId}`);
}

export async function listDatasetVersions(datasetId: string): Promise<DatasetVersion[]> {
  return apiFetch<DatasetVersion[]>(`/datasets/${datasetId}/versions`);
}

export async function getDatasetVersion(versionId: string): Promise<DatasetVersion> {
  return apiFetch<DatasetVersion>(`/dataset-versions/${versionId}`);
}

export async function listTestCases(versionId: string): Promise<TestCase[]> {
  return apiFetch<TestCase[]>(`/dataset-versions/${versionId}/test-cases`);
}
