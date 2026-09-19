import { apiFetch, unwrapPage, type Page } from "@/lib/api/client";
import type { Project } from "@/types/api";

export async function listProjects(): Promise<Project[]> {
  const page = await apiFetch<Page<Project>>("/projects?page_size=200");
  return unwrapPage(page);
}

export async function getProject(projectId: string): Promise<Project> {
  return apiFetch<Project>(`/projects/${projectId}`);
}
