export interface EmailTemplate {
  id: string;
  name: string;
  description: string | null;
  subject: string;
  html_content: string;
  plain_text_content: string | null;
  plain_text_customized: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  warnings: string[];
}

export interface PaginatedTemplates {
  items: EmailTemplate[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface TemplateCreatePayload {
  name: string;
  description?: string | null;
  subject: string;
  html_content: string;
  plain_text_content?: string | null;
  plain_text_customized?: boolean;
  is_active?: boolean;
}

export interface TemplateUpdatePayload {
  name?: string;
  description?: string | null;
  subject?: string;
  html_content?: string;
  plain_text_content?: string | null;
  plain_text_customized?: boolean;
  is_active?: boolean;
}

export interface TemplateRenderResponse {
  rendered_subject: string;
  rendered_html: string;
  rendered_text: string;
  warnings: string[];
  used_variables: string[];
  missing_variables: string[];
  preview_mode: "contact" | "sample";
}

export interface TemplateAsset {
  id: string;
  template_id: string | null;
  original_filename: string;
  mime_type: string;
  file_size: number;
  width: number | null;
  height: number | null;
  content_id: string | null;
  preview_url: string;
  cid_placeholder: string | null;
  created_at: string;
}

export interface TemplateFilters {
  page: number;
  page_size: number;
  search: string;
  sort_by: "created_at" | "updated_at" | "name";
  sort_order: "asc" | "desc";
}
