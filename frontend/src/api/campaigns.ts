import { apiClient } from "@/api/client";
import type {
  Campaign,
  CampaignCreatePayload,
  CampaignFilters,
  CampaignPreview,
  CampaignReview,
  CampaignUpdatePayload,
  CampaignValidation,
  PaginatedCampaigns,
  PaginatedRecipients,
  RecipientSnapshotResponse,
  CampaignStats,
  PaginatedEmailMessages,
  CampaignEmailMessage,
} from "@/types/campaigns";

export async function fetchCampaigns(filters: CampaignFilters): Promise<PaginatedCampaigns> {
  const { data } = await apiClient.get<PaginatedCampaigns>("/api/v1/campaigns", {
    params: {
      page: filters.page,
      page_size: filters.page_size,
      search: filters.search || undefined,
      status: filters.status || undefined,
      sort_by: filters.sort_by,
      sort_order: filters.sort_order,
    },
  });
  return data;
}

export async function fetchCampaign(id: string): Promise<Campaign> {
  const { data } = await apiClient.get<Campaign>(`/api/v1/campaigns/${id}`);
  return data;
}

export async function createCampaign(payload: CampaignCreatePayload): Promise<Campaign> {
  const { data } = await apiClient.post<Campaign>("/api/v1/campaigns", payload);
  return data;
}

export async function updateCampaign(
  id: string,
  payload: CampaignUpdatePayload,
): Promise<Campaign> {
  const { data } = await apiClient.put<Campaign>(`/api/v1/campaigns/${id}`, payload);
  return data;
}

export async function deleteCampaign(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/campaigns/${id}`);
}

export async function cancelCampaign(id: string): Promise<Campaign> {
  const { data } = await apiClient.post<Campaign>(`/api/v1/campaigns/${id}/cancel`);
  return data;
}

export async function returnCampaignToDraft(id: string): Promise<Campaign> {
  const { data } = await apiClient.post<Campaign>(`/api/v1/campaigns/${id}/edit`);
  return data;
}

export async function snapshotRecipients(
  id: string,
  contactListId: string,
): Promise<RecipientSnapshotResponse> {
  const { data } = await apiClient.post<RecipientSnapshotResponse>(
    `/api/v1/campaigns/${id}/recipients/snapshot`,
    { contact_list_id: contactListId },
  );
  return data;
}

export async function fetchCampaignStats(id: string): Promise<CampaignStats> {
  const { data } = await apiClient.get<CampaignStats>(`/api/v1/campaigns/${id}/stats`);
  return data;
}

export async function fetchCampaignRecipients(
  id: string,
  params: { page?: number; page_size?: number; status?: string } = {},
): Promise<PaginatedRecipients> {
  const { data } = await apiClient.get<PaginatedRecipients>(
    `/api/v1/campaigns/${id}/recipients`,
    { params },
  );
  return data;
}

export async function validateCampaign(id: string): Promise<CampaignValidation> {
  const { data } = await apiClient.post<CampaignValidation>(`/api/v1/campaigns/${id}/validate`);
  return data;
}

export async function markCampaignReady(id: string): Promise<Campaign> {
  const { data } = await apiClient.post<Campaign>(`/api/v1/campaigns/${id}/ready`);
  return data;
}

export async function previewCampaign(
  id: string,
  contactId?: string | null,
): Promise<CampaignPreview> {
  const { data } = await apiClient.post<CampaignPreview>(`/api/v1/campaigns/${id}/preview`, {
    contact_id: contactId || null,
  });
  return data;
}

export async function reviewCampaign(id: string): Promise<CampaignReview> {
  const { data } = await apiClient.get<CampaignReview>(`/api/v1/campaigns/${id}/review`);
  return data;
}

export async function startCampaign(id: string): Promise<Campaign> {
  const { data } = await apiClient.post<Campaign>(`/api/v1/campaigns/${id}/start`);
  return data;
}

export async function pauseCampaign(id: string): Promise<Campaign> {
  const { data } = await apiClient.post<Campaign>(`/api/v1/campaigns/${id}/pause`);
  return data;
}

export async function resumeCampaign(id: string): Promise<Campaign> {
  const { data } = await apiClient.post<Campaign>(`/api/v1/campaigns/${id}/resume`);
  return data;
}

export async function fetchCampaignMessages(
  id: string,
  params: { page?: number; page_size?: number; status?: string; search?: string } = {},
): Promise<PaginatedEmailMessages> {
  const { data } = await apiClient.get<PaginatedEmailMessages>(
    `/api/v1/campaigns/${id}/messages`,
    { params },
  );
  return data;
}

export async function fetchCampaignMessage(
  campaignId: string,
  messageId: string,
): Promise<CampaignEmailMessage> {
  const { data } = await apiClient.get<CampaignEmailMessage>(
    `/api/v1/campaigns/${campaignId}/messages/${messageId}`,
  );
  return data;
}
