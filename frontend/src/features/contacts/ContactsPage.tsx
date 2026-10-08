import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronDown,
  Download,
  MoreHorizontal,
  Plus,
  Search,
  Trash2,
  Users,
} from "lucide-react";

import {
  bulkDeleteContacts,
  createContact,
  deleteContact,
  fetchContactStats,
  fetchContacts,
  updateContact,
} from "@/api/contacts";
import {
  createContactList,
  deleteContactList,
  fetchContactLists,
  updateContactList,
} from "@/api/contactLists";
import { createSuppression } from "@/api/suppressions";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PageHeader } from "@/components/PageHeader";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { useToast } from "@/components/Toast";
import {
  ContactFormModal,
  type ContactFormValues,
} from "@/features/contacts/ContactFormModal";
import { formatContactName, formatDate } from "@/features/contacts/contactUtils";
import { ListFormModal, type ListFormValues } from "@/features/contacts/ListFormModal";
import { useDebounce } from "@/hooks/useDebounce";
import type { Contact, ContactFilters, ContactStatus } from "@/types/contacts";
import { getErrorMessage } from "@/utils/errors";
import { cn } from "@/utils/cn";

const defaultFilters: ContactFilters = {
  page: 1,
  page_size: 25,
  search: "",
  status: "",
  company: "",
  contact_list_id: "",
  sort_by: "created_at",
  sort_order: "desc",
};

type Tab = "contacts" | "lists";

export function ContactsPage() {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  const [tab, setTab] = useState<Tab>("contacts");
  const [filters, setFilters] = useState<ContactFilters>(defaultFilters);
  const [searchInput, setSearchInput] = useState("");
  const debouncedSearch = useDebounce(searchInput, 400);

  const activeFilters = useMemo(
    () => ({ ...filters, search: debouncedSearch }),
    [filters, debouncedSearch],
  );

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);

  const [contactModal, setContactModal] = useState<{
    open: boolean;
    mode: "create" | "edit";
    contact?: Contact | null;
  }>({ open: false, mode: "create" });
  const [listModal, setListModal] = useState<{
    open: boolean;
    mode: "create" | "edit";
    listId?: string;
  }>({ open: false, mode: "create" });

  const [contactError, setContactError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  const [confirmDeleteContact, setConfirmDeleteContact] = useState<Contact | null>(null);
  const [confirmBulkDelete, setConfirmBulkDelete] = useState(false);
  const [confirmDeleteList, setConfirmDeleteList] = useState<{
    id: string;
    name: string;
    total: number;
  } | null>(null);

  const listsQuery = useQuery({
    queryKey: ["contact-lists"],
    queryFn: fetchContactLists,
  });

  const statsQuery = useQuery({
    queryKey: ["contacts", "stats"],
    queryFn: fetchContactStats,
  });

  const contactsQuery = useQuery({
    queryKey: ["contacts", activeFilters],
    queryFn: () => fetchContacts(activeFilters),
  });

  const invalidateContacts = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["contacts"] }),
      queryClient.invalidateQueries({ queryKey: ["contact-lists"] }),
    ]);
  };

  const createContactMutation = useMutation({
    mutationFn: ({ listId, values }: { listId: string; values: ContactFormValues }) =>
      createContact(listId, {
        email: values.email,
        first_name: values.first_name || null,
        last_name: values.last_name || null,
        company: values.company || null,
        phone: values.phone || null,
        website: values.website || null,
      }),
    onSuccess: async () => {
      setContactModal({ open: false, mode: "create" });
      setContactError(null);
      pushToast("Contact created");
      await invalidateContacts();
    },
    onError: (error) => setContactError(getErrorMessage(error, "Failed to create contact")),
  });

  const updateContactMutation = useMutation({
    mutationFn: ({ id, values }: { id: string; values: ContactFormValues }) =>
      updateContact(id, {
        email: values.email,
        first_name: values.first_name || null,
        last_name: values.last_name || null,
        company: values.company || null,
        phone: values.phone || null,
        website: values.website || null,
        status: values.status as ContactStatus | undefined,
      }),
    onSuccess: async () => {
      setContactModal({ open: false, mode: "edit" });
      setContactError(null);
      pushToast("Contact updated");
      await invalidateContacts();
    },
    onError: (error) => setContactError(getErrorMessage(error, "Failed to update contact")),
  });

  const deleteContactMutation = useMutation({
    mutationFn: (id: string) => deleteContact(id),
    onSuccess: async () => {
      setConfirmDeleteContact(null);
      pushToast("Contact deleted");
      setSelectedIds(new Set());
      await invalidateContacts();
    },
    onError: (error) => pushToast(getErrorMessage(error, "Failed to delete contact"), "error"),
  });

  const bulkDeleteMutation = useMutation({
    mutationFn: (ids: string[]) => bulkDeleteContacts(ids),
    onSuccess: async (result) => {
      setConfirmBulkDelete(false);
      setSelectedIds(new Set());
      pushToast(`Deleted ${result.deleted} contacts`);
      await invalidateContacts();
    },
    onError: (error) => pushToast(getErrorMessage(error, "Bulk delete failed"), "error"),
  });

  const createListMutation = useMutation({
    mutationFn: (values: ListFormValues) =>
      createContactList({
        name: values.name,
        description: values.description || null,
      }),
    onSuccess: async () => {
      setListModal({ open: false, mode: "create" });
      setListError(null);
      pushToast("List created");
      await queryClient.invalidateQueries({ queryKey: ["contact-lists"] });
      await queryClient.invalidateQueries({ queryKey: ["contacts", "stats"] });
    },
    onError: (error) => setListError(getErrorMessage(error, "Failed to create list")),
  });

  const updateListMutation = useMutation({
    mutationFn: ({ id, values }: { id: string; values: ListFormValues }) =>
      updateContactList(id, {
        name: values.name,
        description: values.description || null,
      }),
    onSuccess: async () => {
      setListModal({ open: false, mode: "edit" });
      setListError(null);
      pushToast("List updated");
      await queryClient.invalidateQueries({ queryKey: ["contact-lists"] });
      await invalidateContacts();
    },
    onError: (error) => setListError(getErrorMessage(error, "Failed to update list")),
  });

  const deleteListMutation = useMutation({
    mutationFn: (id: string) => deleteContactList(id),
    onSuccess: async () => {
      setConfirmDeleteList(null);
      pushToast("List deleted");
      setFilters((prev) => ({ ...prev, contact_list_id: "", page: 1 }));
      await invalidateContacts();
    },
    onError: (error) => pushToast(getErrorMessage(error, "Failed to delete list"), "error"),
  });

  const suppressMutation = useMutation({
    mutationFn: async (contact: Contact) => {
      try {
        await createSuppression(contact.email, "manual suppress from contacts");
      } catch (error) {
        // Already on global list — still mark contact suppressed.
        const status = (error as { response?: { status?: number } })?.response?.status;
        if (status !== 409) {
          throw error;
        }
      }
      return updateContact(contact.id, { status: "suppressed" });
    },
    onSuccess: async () => {
      pushToast("Contact suppressed");
      setMenuOpenId(null);
      await invalidateContacts();
    },
    onError: (error) => pushToast(getErrorMessage(error, "Failed to suppress contact"), "error"),
  });

  const contacts = contactsQuery.data?.items ?? [];
  const lists = listsQuery.data ?? [];
  const stats = statsQuery.data;
  const editingList = lists.find((list) => list.id === listModal.listId) || null;

  const allVisibleSelected =
    contacts.length > 0 && contacts.every((contact) => selectedIds.has(contact.id));

  const toggleSelectAllVisible = () => {
    if (allVisibleSelected) {
      setSelectedIds(new Set());
      return;
    }
    setSelectedIds(new Set(contacts.map((contact) => contact.id)));
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const updateFilter = <K extends keyof ContactFilters>(key: K, value: ContactFilters[K]) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value,
      page: key === "page" ? (value as number) : 1,
    }));
    setSelectedIds(new Set());
  };

  const toggleSort = (field: ContactFilters["sort_by"]) => {
    setFilters((prev) => {
      if (prev.sort_by === field) {
        return {
          ...prev,
          sort_order: prev.sort_order === "asc" ? "desc" : "asc",
          page: 1,
        };
      }
      return { ...prev, sort_by: field, sort_order: "asc", page: 1 };
    });
  };

  return (
    <div>
      <PageHeader
        title="Contacts"
        description="Manage contact lists and individual contacts."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link to="/contacts/import" className="btn-secondary inline-flex items-center">
              <Download className="mr-2 h-4 w-4" />
              Import Contacts
            </Link>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setListError(null);
                setListModal({ open: true, mode: "create" });
              }}
            >
              <Plus className="mr-2 h-4 w-4" />
              New List
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={() => {
                setContactError(null);
                setContactModal({ open: true, mode: "create" });
              }}
            >
              <Plus className="mr-2 h-4 w-4" />
              New Contact
            </button>
          </div>
        }
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Total Contacts" value={stats ? String(stats.total) : "—"} icon={Users} />
        <StatCard label="Active" value={stats ? String(stats.active) : "—"} icon={Users} />
        <StatCard
          label="Unsubscribed"
          value={stats ? String(stats.unsubscribed) : "—"}
          icon={Users}
        />
        <StatCard
          label="Suppressed"
          value={stats ? String(stats.suppressed) : "—"}
          icon={Users}
        />
        <StatCard
          label="Lists"
          value={stats ? String(stats.contact_lists) : "—"}
          icon={Users}
        />
      </div>

      <div className="mb-4 flex gap-2 border-b border-surface-border">
        <button
          type="button"
          className={cn(
            "px-3 py-2 text-sm font-medium",
            tab === "contacts"
              ? "border-b-2 border-brand text-ink"
              : "text-ink-muted hover:text-ink",
          )}
          onClick={() => setTab("contacts")}
        >
          Contacts
        </button>
        <button
          type="button"
          className={cn(
            "px-3 py-2 text-sm font-medium",
            tab === "lists"
              ? "border-b-2 border-brand text-ink"
              : "text-ink-muted hover:text-ink",
          )}
          onClick={() => setTab("lists")}
        >
          Lists
        </button>
      </div>

      {tab === "lists" ? (
        <div className="card overflow-hidden">
          {listsQuery.isLoading ? (
            <div className="space-y-3 p-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-12 animate-pulse rounded-lg bg-surface-muted" />
              ))}
            </div>
          ) : lists.length === 0 ? (
            <div className="p-10 text-center text-sm text-ink-muted">
              No lists yet. Create one to start adding contacts.
            </div>
          ) : (
            <ul className="divide-y divide-surface-border">
              {lists.map((list) => (
                <li key={list.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <button
                      type="button"
                      className="text-sm font-medium text-ink hover:underline"
                      onClick={() => {
                        setTab("contacts");
                        updateFilter("contact_list_id", list.id);
                      }}
                    >
                      {list.name}
                    </button>
                    <p className="mt-1 text-sm text-ink-muted">
                      {list.total_contacts} contacts
                      {list.description ? ` · ${list.description}` : ""}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="btn-secondary px-3 py-2"
                      onClick={() => {
                        setListError(null);
                        setListModal({ open: true, mode: "edit", listId: list.id });
                      }}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="btn-secondary px-3 py-2 text-red-700"
                      onClick={() =>
                        setConfirmDeleteList({
                          id: list.id,
                          name: list.name,
                          total: list.total_contacts,
                        })
                      }
                    >
                      Delete
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="flex flex-col gap-3 border-b border-surface-border p-4 lg:flex-row lg:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" />
              <input
                aria-label="Search contacts"
                className="input pl-9"
                placeholder="Search email, name, company…"
                value={searchInput}
                onChange={(event) => {
                  setSearchInput(event.target.value);
                  setFilters((prev) => ({ ...prev, page: 1 }));
                }}
              />
            </div>
            <select
              aria-label="Filter by status"
              className="input lg:w-40"
              value={filters.status}
              onChange={(event) =>
                updateFilter("status", event.target.value as ContactFilters["status"])
              }
            >
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="invalid">Invalid</option>
              <option value="unsubscribed">Unsubscribed</option>
              <option value="bounced">Bounced</option>
              <option value="suppressed">Suppressed</option>
            </select>
            <select
              aria-label="Filter by list"
              className="input lg:w-48"
              value={filters.contact_list_id}
              onChange={(event) => updateFilter("contact_list_id", event.target.value)}
            >
              <option value="">All lists</option>
              {lists.map((list) => (
                <option key={list.id} value={list.id}>
                  {list.name}
                </option>
              ))}
            </select>
            <input
              aria-label="Filter by company"
              className="input lg:w-44"
              placeholder="Company"
              value={filters.company}
              onChange={(event) => updateFilter("company", event.target.value)}
            />
          </div>

          {selectedIds.size > 0 ? (
            <div className="flex items-center justify-between gap-3 border-b border-surface-border bg-surface-muted/60 px-4 py-3">
              <p className="text-sm text-ink">{selectedIds.size} selected</p>
              <button
                type="button"
                className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700"
                onClick={() => setConfirmBulkDelete(true)}
              >
                <Trash2 className="h-4 w-4" />
                Delete
              </button>
            </div>
          ) : null}

          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-surface-muted/50 text-xs uppercase tracking-wide text-ink-subtle">
                <tr>
                  <th className="px-4 py-3">
                    <input
                      type="checkbox"
                      aria-label="Select all visible contacts"
                      checked={allVisibleSelected}
                      onChange={toggleSelectAllVisible}
                    />
                  </th>
                  {(
                    [
                      ["first_name", "Name"],
                      ["email", "Email"],
                      ["company", "Company"],
                    ] as const
                  ).map(([field, label]) => (
                    <th key={field} className="px-4 py-3 font-medium">
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 hover:text-ink"
                        onClick={() => toggleSort(field)}
                      >
                        {label}
                        <ChevronDown className="h-3.5 w-3.5" />
                      </button>
                    </th>
                  ))}
                  <th className="px-4 py-3 font-medium">List</th>
                  <th className="px-4 py-3 font-medium">
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 hover:text-ink"
                      onClick={() => toggleSort("status")}
                    >
                      Status
                      <ChevronDown className="h-3.5 w-3.5" />
                    </button>
                  </th>
                  <th className="px-4 py-3 font-medium">
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 hover:text-ink"
                      onClick={() => toggleSort("created_at")}
                    >
                      Created
                      <ChevronDown className="h-3.5 w-3.5" />
                    </button>
                  </th>
                  <th className="px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border">
                {contactsQuery.isLoading ? (
                  Array.from({ length: 5 }).map((_, index) => (
                    <tr key={index}>
                      <td colSpan={8} className="px-4 py-3">
                        <div className="h-8 animate-pulse rounded bg-surface-muted" />
                      </td>
                    </tr>
                  ))
                ) : contactsQuery.isError ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-10 text-center text-sm text-red-600">
                      {getErrorMessage(contactsQuery.error, "Failed to load contacts")}
                    </td>
                  </tr>
                ) : contacts.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-12 text-center text-sm text-ink-muted">
                      No contacts found. Create a list and add your first contact.
                    </td>
                  </tr>
                ) : (
                  contacts.map((contact) => (
                    <tr key={contact.id} className="hover:bg-surface-muted/40">
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          aria-label={`Select ${contact.email}`}
                          checked={selectedIds.has(contact.id)}
                          onChange={() => toggleSelect(contact.id)}
                        />
                      </td>
                      <td className="px-4 py-3 font-medium text-ink">
                        {formatContactName(contact)}
                      </td>
                      <td className="px-4 py-3 text-ink-muted">{contact.email}</td>
                      <td className="px-4 py-3 text-ink-muted">{contact.company || "—"}</td>
                      <td className="px-4 py-3 text-ink-muted">
                        {contact.contact_list_name || "—"}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={contact.status} />
                      </td>
                      <td className="px-4 py-3 text-ink-muted">
                        {formatDate(contact.created_at)}
                      </td>
                      <td className="relative px-4 py-3">
                        <button
                          type="button"
                          className="rounded-md p-1.5 text-ink-muted hover:bg-surface-muted"
                          aria-label="Contact actions"
                          onClick={() =>
                            setMenuOpenId((prev) => (prev === contact.id ? null : contact.id))
                          }
                        >
                          <MoreHorizontal className="h-4 w-4" />
                        </button>
                        {menuOpenId === contact.id ? (
                          <div className="absolute right-4 z-10 mt-1 w-40 rounded-lg border border-surface-border bg-surface py-1 shadow-card">
                            <button
                              type="button"
                              className="block w-full px-3 py-2 text-left text-sm hover:bg-surface-muted"
                              onClick={() => {
                                setContactError(null);
                                setContactModal({
                                  open: true,
                                  mode: "edit",
                                  contact,
                                });
                                setMenuOpenId(null);
                              }}
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              className="block w-full px-3 py-2 text-left text-sm hover:bg-surface-muted"
                              onClick={() => suppressMutation.mutate(contact)}
                            >
                              Suppress
                            </button>
                            <button
                              type="button"
                              className="block w-full px-3 py-2 text-left text-sm text-red-700 hover:bg-surface-muted"
                              onClick={() => {
                                setConfirmDeleteContact(contact);
                                setMenuOpenId(null);
                              }}
                            >
                              Delete
                            </button>
                          </div>
                        ) : null}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="flex flex-col gap-3 border-t border-surface-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-ink-muted">
              {contactsQuery.data
                ? `Showing page ${contactsQuery.data.page} of ${Math.max(contactsQuery.data.total_pages, 1)} · ${contactsQuery.data.total} total`
                : "—"}
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                className="btn-secondary px-3 py-2"
                disabled={!contactsQuery.data || filters.page <= 1}
                onClick={() => updateFilter("page", filters.page - 1)}
              >
                Previous
              </button>
              <button
                type="button"
                className="btn-secondary px-3 py-2"
                disabled={
                  !contactsQuery.data ||
                  filters.page >= (contactsQuery.data.total_pages || 1)
                }
                onClick={() => updateFilter("page", filters.page + 1)}
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}

      <ContactFormModal
        open={contactModal.open}
        mode={contactModal.mode}
        lists={lists}
        initial={contactModal.contact}
        defaultListId={filters.contact_list_id || lists[0]?.id}
        submitting={createContactMutation.isPending || updateContactMutation.isPending}
        serverError={contactError}
        onClose={() => setContactModal({ open: false, mode: "create" })}
        onSubmit={async (values) => {
          if (contactModal.mode === "edit" && contactModal.contact) {
            await updateContactMutation.mutateAsync({
              id: contactModal.contact.id,
              values,
            });
          } else {
            await createContactMutation.mutateAsync({
              listId: values.contact_list_id,
              values,
            });
          }
        }}
      />

      <ListFormModal
        open={listModal.open}
        mode={listModal.mode}
        initial={editingList}
        submitting={createListMutation.isPending || updateListMutation.isPending}
        serverError={listError}
        onClose={() => setListModal({ open: false, mode: "create" })}
        onSubmit={async (values) => {
          if (listModal.mode === "edit" && listModal.listId) {
            await updateListMutation.mutateAsync({ id: listModal.listId, values });
          } else {
            await createListMutation.mutateAsync(values);
          }
        }}
      />

      <ConfirmDialog
        open={Boolean(confirmDeleteContact)}
        title="Delete contact?"
        description={
          confirmDeleteContact
            ? `This will permanently remove:\n${formatContactName(confirmDeleteContact)}\n${confirmDeleteContact.email}`
            : ""
        }
        confirmLabel="Delete"
        destructive
        loading={deleteContactMutation.isPending}
        onCancel={() => setConfirmDeleteContact(null)}
        onConfirm={() => {
          if (confirmDeleteContact) deleteContactMutation.mutate(confirmDeleteContact.id);
        }}
      />

      <ConfirmDialog
        open={confirmBulkDelete}
        title={`Delete ${selectedIds.size} contacts?`}
        description="Selected contacts will be permanently removed. This cannot be undone."
        confirmLabel="Delete"
        destructive
        loading={bulkDeleteMutation.isPending}
        onCancel={() => setConfirmBulkDelete(false)}
        onConfirm={() => bulkDeleteMutation.mutate([...selectedIds])}
      />

      <ConfirmDialog
        open={Boolean(confirmDeleteList)}
        title="Delete contact list?"
        description={
          confirmDeleteList
            ? `“${confirmDeleteList.name}” and all ${confirmDeleteList.total} contacts in this list will be permanently deleted.`
            : ""
        }
        confirmLabel="Delete list"
        destructive
        loading={deleteListMutation.isPending}
        onCancel={() => setConfirmDeleteList(null)}
        onConfirm={() => {
          if (confirmDeleteList) deleteListMutation.mutate(confirmDeleteList.id);
        }}
      />
    </div>
  );
}
