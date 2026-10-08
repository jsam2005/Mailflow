import { apiClient } from "@/api/client";

export interface SuppressionRow {
  id: string;
  email: string;
  normalized_email: string;
  reason: string;
  source: string | null;
  created_at: string;
}

export async function createSuppression(email: string, notes?: string): Promise<SuppressionRow> {
  const { data } = await apiClient.post<SuppressionRow>("/api/v1/suppressions", {
    email,
    reason: "manual",
    notes,
  });
  return data;
}
