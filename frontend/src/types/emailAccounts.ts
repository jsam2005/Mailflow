export type ConnectionStatus = "connected" | "expired" | "error" | "disconnected";

export interface EmailAccount {
  id: string;
  provider: string;
  email_address: string;
  display_name: string | null;
  daily_send_limit: number;
  hourly_send_limit: number;
  minimum_delay_seconds: number;
  maximum_delay_seconds: number;
  sent_today: number;
  connection_status: ConnectionStatus;
  last_connection_check_at: string | null;
  last_connection_error: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmailAccountListResponse {
  items: EmailAccount[];
}

export interface GoogleConnectResponse {
  authorization_url: string;
}

export interface ConnectionTestResponse {
  connected: boolean;
  email_address?: string | null;
  message: string;
}

export interface EmailAccountUpdatePayload {
  daily_send_limit?: number;
  hourly_send_limit?: number;
  minimum_delay_seconds?: number;
  maximum_delay_seconds?: number;
}

export interface SendTestEmailPayload {
  to_email: string;
  mode: "simple" | "template";
  subject?: string;
  message?: string;
  template_id?: string;
  contact_id?: string;
}

export interface SendTestEmailResponse {
  sent: boolean;
  to_email: string;
  subject: string;
  provider_message_id?: string | null;
  thread_id?: string | null;
  timestamp: string;
  message: string;
}
