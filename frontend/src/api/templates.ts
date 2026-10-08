import { apiClient } from "@/api/client";
import type {
  EmailTemplate,
  PaginatedTemplates,
  TemplateCreatePayload,
  TemplateFilters,
  TemplateRenderResponse,
  TemplateUpdatePayload,
} from "@/types/templates";

export async function fetchTemplates(filters: TemplateFilters): Promise<PaginatedTemplates> {
  const { data } = await apiClient.get<PaginatedTemplates>("/api/v1/templates", {
    params: {
      page: filters.page,
      page_size: filters.page_size,
      search: filters.search || undefined,
      sort_by: filters.sort_by,
      sort_order: filters.sort_order,
    },
  });
  return data;
}

export async function fetchTemplate(id: string): Promise<EmailTemplate> {
  const { data } = await apiClient.get<EmailTemplate>(`/api/v1/templates/${id}`);
  return data;
}

export async function createTemplate(payload: TemplateCreatePayload): Promise<EmailTemplate> {
  const { data } = await apiClient.post<EmailTemplate>("/api/v1/templates", payload);
  return data;
}

export async function updateTemplate(
  id: string,
  payload: TemplateUpdatePayload,
): Promise<EmailTemplate> {
  const { data } = await apiClient.put<EmailTemplate>(`/api/v1/templates/${id}`, payload);
  return data;
}

export async function deleteTemplate(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/templates/${id}`);
}

export async function duplicateTemplate(id: string): Promise<EmailTemplate> {
  const { data } = await apiClient.post<EmailTemplate>(`/api/v1/templates/${id}/duplicate`);
  return data;
}

export async function renderTemplate(
  id: string,
  payload: { contact_id?: string | null; sample_data?: Record<string, unknown> | null },
): Promise<TemplateRenderResponse> {
  const { data } = await apiClient.post<TemplateRenderResponse>(
    `/api/v1/templates/${id}/render`,
    payload,
  );
  return data;
}

export async function renderTemplatePreview(payload: {
  subject: string;
  html_content: string;
  plain_text_content?: string | null;
  contact_id?: string | null;
  sample_data?: Record<string, unknown> | null;
}): Promise<TemplateRenderResponse> {
  const { data } = await apiClient.post<TemplateRenderResponse>(
    "/api/v1/templates/render-preview",
    payload,
  );
  return data;
}
