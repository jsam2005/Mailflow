export type CampaignStatus =
  | "draft"
  | "ready"
  | "cancelled"
  | "running"
  | "paused"
  | "completed";

export interface AccountSummary {
  id: string;
  email_address: string;
  provider: string;
  connection_status: string;
  daily_send_limit: number;
  hourly_send_limit: number;
  minimum_delay_seconds: number;
  maximum_delay_seconds: number;
  is_active: boolean;
}

export interface TemplateSummary {
  id: string;
  name: string;
  subject: string;
}

export interface ContactListSummary {
  id: string;
  name: string;
  total_contacts: number;
}

export interface EffectiveLimits {
  daily_limit: number;
  hourly_limit: number;
  minimum_delay_seconds: number;
  maximum_delay_seconds: number;
  inherited_from_account: boolean;
}

export interface CampaignStats {
  total: number;
  total_recipients?: number;
  eligible: number;
  pending: number;
  excluded: number;
  invalid: number;
  suppressed: number;
  queued: number;
  sending?: number;
  sent: number;
  failed: number;
  cancelled?: number;
  replied: number;
  messages_total?: number;
  messages_queued?: number;
  messages_sending?: number;
  messages_sent?: number;
  messages_failed?: number;
  messages_cancelled?: number;
  progress_percent?: number;
  started_at?: string | null;
  completed_at?: string | null;
  last_activity_at?: string | null;
}

export interface Campaign {
  id: string;
  name: string;
  description: string | null;
  status: CampaignStatus;
  email_account_id: string | null;
  template_id: string | null;
  contact_list_id: string | null;
  subject_override: string | null;
  html_override: string | null;
  plain_text_override: string | null;
  has_content_snapshot: boolean;
  snapshot_subject: string | null;
  daily_limit: number | null;
  hourly_limit: number | null;
  minimum_delay_seconds: number | null;
  maximum_delay_seconds: number | null;
  stop_on_reply: boolean;
  skip_suppressed: boolean;
  ready_at: string | null;
  started_at?: string | null;
  paused_at?: string | null;
  completed_at?: string | null;
  cancelled_at: string | null;
  last_activity_at?: string | null;
  created_at: string;
  updated_at: string;
  email_account?: AccountSummary | null;
  template?: TemplateSummary | null;
  contact_list?: ContactListSummary | null;
  stats?: CampaignStats | null;
  effective_limits?: EffectiveLimits | null;
  content_source?: string | null;
}

export interface PaginatedCampaigns {
  items: Campaign[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface CampaignFilters {
  page: number;
  page_size: number;
  search: string;
  status: CampaignStatus | "";
  sort_by: "created_at" | "updated_at" | "name" | "status";
  sort_order: "asc" | "desc";
}

export interface CampaignCreatePayload {
  name: string;
  description?: string | null;
}

export interface CampaignUpdatePayload {
  name?: string;
  description?: string | null;
  email_account_id?: string | null;
  template_id?: string | null;
  contact_list_id?: string | null;
  subject_override?: string | null;
  html_override?: string | null;
  plain_text_override?: string | null;
  clear_overrides?: boolean;
  daily_limit?: number | null;
  hourly_limit?: number | null;
  minimum_delay_seconds?: number | null;
  maximum_delay_seconds?: number | null;
  stop_on_reply?: boolean;
  skip_suppressed?: boolean;
  use_custom_content?: boolean;
}

export interface RecipientSnapshotResponse {
  contact_list_id: string;
  total: number;
  eligible: number;
  invalid: number;
  suppressed: number;
  excluded: number;
  stats: CampaignStats;
}

export interface CampaignValidation {
  valid: boolean;
  errors: string[];
  warnings: string[];
  eligible_recipients: number;
}

export interface CampaignPreview {
  contact_id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  company: string | null;
  rendered_subject: string;
  rendered_html: string;
  rendered_text: string;
  warnings: string[];
  has_previous: boolean;
  has_next: boolean;
  previous_contact_id: string | null;
  next_contact_id: string | null;
  position: number;
  total_eligible: number;
}

export interface CampaignReview {
  campaign: Campaign;
  validation: CampaignValidation;
  message: string;
}

export interface CampaignRecipient {
  id: string;
  campaign_id: string;
  contact_id: string;
  status: string;
  exclusion_reason: string | null;
  email: string | null;
  first_name: string | null;
  last_name: string | null;
  company: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedRecipients {
  items: CampaignRecipient[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface CampaignEmailMessage {
  id: string;
  campaign_id: string;
  campaign_recipient_id: string;
  contact_id: string;
  email_account_id: string;
  to_email: string;
  to_name: string | null;
  subject: string;
  rendered_html: string;
  rendered_text: string | null;
  status: string;
  provider_message_id: string | null;
  attempt_count: number;
  max_attempts: number;
  sent_at: string | null;
  failed_at: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedEmailMessages {
  items: CampaignEmailMessage[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}
