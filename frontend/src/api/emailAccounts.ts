import { apiClient } from "@/api/client";
import type {
  ConnectionTestResponse,
  EmailAccount,
  EmailAccountListResponse,
  EmailAccountUpdatePayload,
  GoogleConnectResponse,
  SendTestEmailPayload,
  SendTestEmailResponse,
} from "@/types/emailAccounts";

export async function fetchEmailAccounts(): Promise<EmailAccountListResponse> {
  const { data } = await apiClient.get<EmailAccountListResponse>("/api/v1/email-accounts");
  return data;
}

export async function connectGoogle(): Promise<GoogleConnectResponse> {
  const { data } = await apiClient.post<GoogleConnectResponse>(
    "/api/v1/email-accounts/google/connect",
  );
  return data;
}

export async function reconnectEmailAccount(id: string): Promise<GoogleConnectResponse> {
  const { data } = await apiClient.post<GoogleConnectResponse>(
    `/api/v1/email-accounts/${id}/reconnect`,
  );
  return data;
}

export async function updateEmailAccount(
  id: string,
  payload: EmailAccountUpdatePayload,
): Promise<EmailAccount> {
  const { data } = await apiClient.put<EmailAccount>(`/api/v1/email-accounts/${id}`, payload);
  return data;
}

export async function disconnectEmailAccount(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/email-accounts/${id}`);
}

export async function testEmailAccountConnection(id: string): Promise<ConnectionTestResponse> {
  const { data } = await apiClient.post<ConnectionTestResponse>(
    `/api/v1/email-accounts/${id}/test-connection`,
  );
  return data;
}

export async function sendTestEmail(
  id: string,
  payload: SendTestEmailPayload,
): Promise<SendTestEmailResponse> {
  const { data } = await apiClient.post<SendTestEmailResponse>(
    `/api/v1/email-accounts/${id}/send-test`,
    payload,
  );
  return data;
}
