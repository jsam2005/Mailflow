import { apiClient, getStoredToken } from "@/api/client";
import type { TemplateAsset } from "@/types/templates";

export async function uploadTemplateAsset(
  file: File,
  templateId?: string | null,
): Promise<TemplateAsset> {
  const form = new FormData();
  form.append("file", file);
  if (templateId) {
    form.append("template_id", templateId);
  }
  const { data } = await apiClient.post<TemplateAsset>("/api/v1/template-assets", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

/** Relative/absolute URL for editor <img> preview (token query for browser loads). */
export function templateAssetContentUrl(assetId: string): string {
  const token = getStoredToken();
  const path = `/api/v1/template-assets/${assetId}/content`;
  const base = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "";
  const url = `${base}${path}`;
  if (!token) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}access_token=${encodeURIComponent(token)}`;
}

export function authImageHeaders(): Record<string, string> {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
