import { apiClient } from "@/api/client";
import type {
  ContactList,
  ContactListCreatePayload,
  ContactListUpdatePayload,
} from "@/types/contacts";

export async function fetchContactLists(): Promise<ContactList[]> {
  const { data } = await apiClient.get<ContactList[]>("/api/v1/contact-lists");
  return data;
}

export async function createContactList(
  payload: ContactListCreatePayload,
): Promise<ContactList> {
  const { data } = await apiClient.post<ContactList>("/api/v1/contact-lists", payload);
  return data;
}

export async function updateContactList(
  listId: string,
  payload: ContactListUpdatePayload,
): Promise<ContactList> {
  const { data } = await apiClient.put<ContactList>(
    `/api/v1/contact-lists/${listId}`,
    payload,
  );
  return data;
}

export async function deleteContactList(listId: string): Promise<void> {
  await apiClient.delete(`/api/v1/contact-lists/${listId}`);
}
