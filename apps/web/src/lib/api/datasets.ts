import { apiFetch, unwrapPage, type Page } from "@/lib/api/client";
import type { Dataset, DatasetVersion, TestCase } from "@/types/api";

export async function listDatasets(projectId: string): Promise<Dataset[]> {
  const page = await apiFetch<Page<Dataset>>(`/projects/${projectId}/datasets?page_size=200`);
  return unwrapPage(page);
}

export async function getDataset(datasetId: string): Promise<Dataset> {
  return apiFetch<Dataset>(`/datasets/${datasetId}`);
}

export async function listDatasetVersions(datasetId: string): Promise<DatasetVersion[]> {
  const page = await apiFetch<Page<DatasetVersion>>(
    `/datasets/${datasetId}/versions?page_size=200`,
  );
  return unwrapPage(page);
}

export async function getDatasetVersion(versionId: string): Promise<DatasetVersion> {
  return apiFetch<DatasetVersion>(`/dataset-versions/${versionId}`);
}

export async function listTestCases(versionId: string): Promise<TestCase[]> {
  const page = await apiFetch<Page<TestCase>>(
    `/dataset-versions/${versionId}/test-cases?page_size=200`,
  );
  return unwrapPage(page);
}
