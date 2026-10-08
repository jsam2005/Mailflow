import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/Toast";
import { ContactsPage } from "@/features/contacts/ContactsPage";

vi.mock("@/api/contacts", () => ({
  fetchContacts: vi.fn().mockResolvedValue({
    items: [],
    page: 1,
    page_size: 25,
    total: 0,
    total_pages: 0,
  }),
  fetchContactStats: vi.fn().mockResolvedValue({
    total: 0,
    active: 0,
    invalid: 0,
    unsubscribed: 0,
    bounced: 0,
    suppressed: 0,
    contact_lists: 0,
  }),
  createContact: vi.fn(),
  updateContact: vi.fn(),
  deleteContact: vi.fn(),
  bulkDeleteContacts: vi.fn(),
}));

vi.mock("@/api/contactLists", () => ({
  fetchContactLists: vi.fn().mockResolvedValue([
    {
      id: "list-1",
      name: "Outbound",
      description: null,
      original_filename: null,
      total_contacts: 0,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
  ]),
  createContactList: vi.fn(),
  updateContactList: vi.fn(),
  deleteContactList: vi.fn(),
}));

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <ToastProvider>
          <ContactsPage />
        </ToastProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("ContactsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders contacts heading and actions", async () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Contacts" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /New Contact/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /New List/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Import Contacts/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Import Contacts/i })).toHaveAttribute(
      "href",
      "/contacts/import",
    );
    await waitFor(() => {
      expect(screen.getByText(/No contacts found/i)).toBeInTheDocument();
    });
  });

  it("renders search and filters", async () => {
    renderPage();
    expect(screen.getByLabelText(/Search contacts/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Filter by status/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Filter by list/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("option", { name: "Outbound" })).toBeInTheDocument();
    });
  });

  it("opens new contact modal and validates email", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /New Contact/i }));
    expect(screen.getByRole("dialog", { name: /New contact/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Create contact/i }));
    await waitFor(() => {
      expect(screen.getByText(/Enter a valid email/i)).toBeInTheDocument();
    });
  });

  it("shows delete list confirmation copy", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /^Lists$/i }));
    await waitFor(() => {
      expect(screen.getByText("Outbound")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /^Delete$/i }));
    expect(screen.getByRole("dialog", { name: /Delete contact list/i })).toBeInTheDocument();
    expect(
      screen.getByText(/all 0 contacts in this list will be permanently deleted/i),
    ).toBeInTheDocument();
  });
});
