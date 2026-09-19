import { apiFetch } from "@/lib/api/client";
import type { Project } from "@/types/api";

export async function listProjects(): Promise<Project[]> {
  return apiFetch<Project[]>("/projects");
}

export async function getProject(projectId: string): Promise<Project> {
  return apiFetch<Project>(`/projects/${projectId}`);
}
