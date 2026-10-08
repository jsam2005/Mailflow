export type ContactStatus =
  | "active"
  | "invalid"
  | "unsubscribed"
  | "bounced"
  | "suppressed";

export interface ContactList {
  id: string;
  name: string;
  description: string | null;
  original_filename: string | null;
  total_contacts: number;
  created_at: string;
  updated_at: string;
}

export interface Contact {
  id: string;
  contact_list_id: string;
  contact_list_name: string | null;
  email: string;
  first_name: string | null;
  last_name: string | null;
  company: string | null;
  phone: string | null;
  website: string | null;
  status: ContactStatus;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface PaginatedContacts {
  items: Contact[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface ContactStats {
  total: number;
  active: number;
  invalid: number;
  unsubscribed: number;
  bounced: number;
  suppressed: number;
  contact_lists: number;
}

export interface ContactListCreatePayload {
  name: string;
  description?: string | null;
}

export interface ContactListUpdatePayload {
  name?: string;
  description?: string | null;
}

export interface ContactCreatePayload {
  email: string;
  first_name?: string | null;
  last_name?: string | null;
  company?: string | null;
  phone?: string | null;
  website?: string | null;
  metadata?: Record<string, unknown>;
}

export interface ContactUpdatePayload {
  email?: string;
  first_name?: string | null;
  last_name?: string | null;
  company?: string | null;
  phone?: string | null;
  website?: string | null;
  status?: ContactStatus;
  metadata?: Record<string, unknown>;
}

export interface ContactFilters {
  page: number;
  page_size: number;
  search: string;
  status: ContactStatus | "";
  company: string;
  contact_list_id: string;
  sort_by: "created_at" | "email" | "first_name" | "last_name" | "company" | "status";
  sort_order: "asc" | "desc";
}
