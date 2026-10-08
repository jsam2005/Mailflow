import type { Contact } from "@/types/contacts";

export function formatContactName(contact: Pick<Contact, "first_name" | "last_name">): string {
  const name = [contact.first_name, contact.last_name].filter(Boolean).join(" ").trim();
  return name || "—";
}

export function formatDate(value: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    }).format(new Date(value));
  } catch {
    return value;
  }
}
