"use server";

import { revalidatePath } from "next/cache";
import { apiFetch, unwrapPage, type Page } from "@/lib/api/client";
import type { ApiKeyCreated, ApiKeyMeta } from "@/types/api";

export type CreateApiKeyResult =
  | { ok: true; created: ApiKeyCreated }
  | { ok: false; error: string };

export type RevokeApiKeyResult = { ok: true } | { ok: false; error: string };

export async function createProjectApiKey(
  projectId: string,
  name: string,
): Promise<CreateApiKeyResult> {
  const trimmed = name.trim();
  if (!trimmed) {
    return { ok: false, error: "Name is required" };
  }
  try {
    const created = await apiFetch<ApiKeyCreated>(`/projects/${projectId}/api-keys`, {
      method: "POST",
      body: { name: trimmed },
    });
    revalidatePath(`/projects/${projectId}/settings/api-keys`);
    return { ok: true, created };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Failed to create API key",
    };
  }
}

export async function revokeProjectApiKey(
  projectId: string,
  keyId: string,
): Promise<RevokeApiKeyResult> {
  try {
    await apiFetch<void>(`/projects/${projectId}/api-keys/${keyId}`, {
      method: "DELETE",
    });
    revalidatePath(`/projects/${projectId}/settings/api-keys`);
    return { ok: true };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Failed to revoke API key",
    };
  }
}

export async function listProjectApiKeys(projectId: string): Promise<ApiKeyMeta[]> {
  const page = await apiFetch<Page<ApiKeyMeta>>(`/projects/${projectId}/api-keys?page_size=200`);
  return unwrapPage(page);
}
