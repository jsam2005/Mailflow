import { apiClient } from "@/api/client";
import type {
  Contact,
  ContactCreatePayload,
  ContactFilters,
  ContactStats,
  ContactUpdatePayload,
  PaginatedContacts,
} from "@/types/contacts";

export async function fetchContacts(filters: ContactFilters): Promise<PaginatedContacts> {
  const { data } = await apiClient.get<PaginatedContacts>("/api/v1/contacts", {
    params: {
      page: filters.page,
      page_size: filters.page_size,
      search: filters.search || undefined,
      status: filters.status || undefined,
      company: filters.company || undefined,
      contact_list_id: filters.contact_list_id || undefined,
      sort_by: filters.sort_by,
      sort_order: filters.sort_order,
    },
  });
  return data;
}

export async function fetchContactStats(): Promise<ContactStats> {
  const { data } = await apiClient.get<ContactStats>("/api/v1/contacts/stats");
  return data;
}

export async function createContact(
  listId: string,
  payload: ContactCreatePayload,
): Promise<Contact> {
  const { data } = await apiClient.post<Contact>(
    `/api/v1/contact-lists/${listId}/contacts`,
    payload,
  );
  return data;
}

export async function updateContact(
  contactId: string,
  payload: ContactUpdatePayload,
): Promise<Contact> {
  const { data } = await apiClient.put<Contact>(`/api/v1/contacts/${contactId}`, payload);
  return data;
}

export async function deleteContact(contactId: string): Promise<void> {
  await apiClient.delete(`/api/v1/contacts/${contactId}`);
}

export async function bulkDeleteContacts(contactIds: string[]): Promise<{ deleted: number }> {
  const { data } = await apiClient.post<{ deleted: number }>("/api/v1/contacts/bulk-delete", {
    contact_ids: contactIds,
  });
  return data;
}
