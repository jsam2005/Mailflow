import { apiClient } from "@/api/client";
import type {
  ImportExecuteResponse,
  ImportSession,
  ImportUploadResponse,
  ImportValidationResponse,
} from "@/types/imports";

export async function uploadImportFile(file: File): Promise<ImportUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post<ImportUploadResponse>("/api/v1/imports/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function previewImport(
  importId: string,
  sheet?: string,
): Promise<ImportUploadResponse> {
  const { data } = await apiClient.get<ImportUploadResponse>(
    `/api/v1/imports/${importId}/preview`,
    { params: sheet ? { sheet } : undefined },
  );
  return data;
}

export async function validateImport(
  importId: string,
  payload: {
    column_mapping: Record<string, string>;
    sheet?: string | null;
    contact_list_id?: string | null;
  },
): Promise<ImportValidationResponse> {
  const { data } = await apiClient.post<ImportValidationResponse>(
    `/api/v1/imports/${importId}/validate`,
    payload,
  );
  return data;
}

export async function executeImport(
  importId: string,
  payload: {
    contact_list_id?: string | null;
    column_mapping?: Record<string, string>;
    sheet?: string | null;
    new_list_name?: string | null;
    new_list_description?: string | null;
  },
): Promise<ImportExecuteResponse> {
  const { data } = await apiClient.post<ImportExecuteResponse>(
    `/api/v1/imports/${importId}/execute`,
    payload,
  );
  return data;
}

export async function cancelImport(importId: string): Promise<ImportSession> {
  const { data } = await apiClient.post<ImportSession>(`/api/v1/imports/${importId}/cancel`);
  return data;
}

export async function fetchImportHistory(): Promise<ImportSession[]> {
  const { data } = await apiClient.get<ImportSession[]>("/api/v1/imports");
  return data;
}

export async function fetchImportSession(importId: string): Promise<ImportSession> {
  const { data } = await apiClient.get<ImportSession>(`/api/v1/imports/${importId}`);
  return data;
}
