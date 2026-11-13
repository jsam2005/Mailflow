import { apiClient } from "@/api/client";
import type { LoginRequest, TokenResponse, User } from "@/types/auth";

export async function login(payload: LoginRequest): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/api/v1/auth/login", payload);
  return data;
}

export async function fetchCurrentUser(): Promise<User> {
  const { data } = await apiClient.get<User>("/api/v1/auth/me");
  return data;
}

/** Desktop exe only: open a session for the local admin without a login form. */
export async function desktopSession(): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/api/v1/auth/desktop-session", null, {
    headers: { "X-MailFlow-Desktop": "1" },
  });
  return data;
}
