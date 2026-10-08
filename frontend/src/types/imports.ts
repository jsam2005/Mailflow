export type ImportStatus =
  | "uploaded"
  | "mapped"
  | "validated"
  | "importing"
  | "completed"
  | "failed"
  | "cancelled";

export type MappingTarget =
  | "ignore"
  | "email"
  | "first_name"
  | "last_name"
  | "full_name"
  | "company"
  | "phone"
  | "website"
  | "custom";

export interface ImportUploadResponse {
  import_session_id: string;
  original_filename: string;
  file_type: string;
  total_rows: number;
  columns: string[];
  preview_rows: Record<string, string | null>[];
  suggested_mapping: Record<string, string>;
  sheets: string[];
  default_sheet: string | null;
  status: ImportStatus;
}

export interface ImportIssueRow {
  row_number: number;
  email: string | null;
  reason: string;
  first_name: string | null;
  last_name: string | null;
  company: string | null;
}

export interface ImportValidationResponse {
  total_rows: number;
  valid_rows: number;
  invalid_email_rows: number;
  missing_email_rows: number;
  duplicate_in_file_rows: number;
  duplicate_existing_rows: number;
  importable_rows: number;
  skipped_rows: number;
  sample_invalid_emails: ImportIssueRow[];
  sample_missing_emails: ImportIssueRow[];
  sample_duplicates_in_file: ImportIssueRow[];
  sample_duplicates_existing: ImportIssueRow[];
}

export interface ImportExecuteResponse {
  import_session_id: string;
  contact_list_id: string;
  contact_list_name: string;
  status: ImportStatus;
  imported_rows: number;
  skipped_rows: number;
  total_rows: number;
  invalid_email_rows: number;
  missing_email_rows: number;
  duplicate_in_file_rows: number;
  duplicate_existing_rows: number;
}

export interface ImportSession {
  id: string;
  contact_list_id: string | null;
  contact_list_name: string | null;
  original_filename: string;
  file_type: string;
  status: ImportStatus;
  selected_sheet: string | null;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  duplicate_rows: number;
  missing_email_rows: number;
  imported_rows: number;
  skipped_rows: number;
  column_mapping: Record<string, string> | null;
  validation_summary: ImportValidationResponse | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}
