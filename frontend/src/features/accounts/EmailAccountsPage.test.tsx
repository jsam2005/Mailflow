import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/Toast";
import { EmailAccountsPage } from "@/features/accounts/EmailAccountsPage";
import type { EmailAccount } from "@/types/emailAccounts";

const mockAccount: EmailAccount = {
  id: "acc-1",
  provider: "gmail",
  email_address: "hello@example.com",
  display_name: "Hello",
  daily_send_limit: 100,
  hourly_send_limit: 20,
  minimum_delay_seconds: 30,
  maximum_delay_seconds: 90,
  sent_today: 2,
  connection_status: "connected",
  last_connection_check_at: "2026-10-07T10:00:00Z",
  last_connection_error: null,
  is_active: true,
  created_at: "2026-10-07T09:00:00Z",
  updated_at: "2026-10-07T10:00:00Z",
};

const fetchEmailAccounts = vi.fn();
const connectGoogle = vi.fn();
const testEmailAccountConnection = vi.fn();
const disconnectEmailAccount = vi.fn();
const updateEmailAccount = vi.fn();
const sendTestEmail = vi.fn();
const reconnectEmailAccount = vi.fn();

vi.mock("@/api/emailAccounts", () => ({
  fetchEmailAccounts: (...args: unknown[]) => fetchEmailAccounts(...args),
  connectGoogle: (...args: unknown[]) => connectGoogle(...args),
  testEmailAccountConnection: (...args: unknown[]) => testEmailAccountConnection(...args),
  disconnectEmailAccount: (...args: unknown[]) => disconnectEmailAccount(...args),
  updateEmailAccount: (...args: unknown[]) => updateEmailAccount(...args),
  sendTestEmail: (...args: unknown[]) => sendTestEmail(...args),
  reconnectEmailAccount: (...args: unknown[]) => reconnectEmailAccount(...args),
}));

vi.mock("@/api/templates", () => ({
  fetchTemplates: vi.fn().mockResolvedValue({
    items: [{ id: "t1", name: "Welcome", subject: "Hi" }],
    page: 1,
    page_size: 100,
    total: 1,
    total_pages: 1,
  }),
  renderTemplate: vi.fn().mockResolvedValue({
    rendered_subject: "Hi Arun",
    rendered_html: "<p>Hello Arun</p>",
    rendered_text: "Hello Arun",
    warnings: [],
    used_variables: ["first_name"],
    missing_variables: [],
  }),
}));

vi.mock("@/api/contacts", () => ({
  fetchContacts: vi.fn().mockResolvedValue({
    items: [{ id: "c1", email: "arun@example.com", first_name: "Arun" }],
    page: 1,
    page_size: 100,
    total: 1,
    total_pages: 1,
  }),
}));

function renderPage(initialEntry = "/email-accounts") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <QueryClientProvider client={client}>
        <ToastProvider>
          <Routes>
            <Route path="/email-accounts" element={<EmailAccountsPage />} />
          </Routes>
        </ToastProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("EmailAccountsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchEmailAccounts.mockResolvedValue({ items: [] });
    connectGoogle.mockResolvedValue({
      authorization_url: "https://accounts.google.com/o/oauth2/v2/auth?x=1",
    });
    testEmailAccountConnection.mockResolvedValue({
      connected: true,
      message: "Gmail connection is working.",
    });
  });

  it("renders heading and empty state", async () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Email Accounts" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/No email accounts connected/i)).toBeInTheDocument();
    });
    expect(screen.getAllByRole("button", { name: /Connect Gmail/i }).length).toBeGreaterThan(0);
  });

  it("starts Connect Gmail OAuth", async () => {
    const assign = vi.fn();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...window.location, assign },
    });
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText(/No email accounts connected/i));
    await user.click(screen.getAllByRole("button", { name: /Connect Gmail/i })[0]);
    await waitFor(() => expect(connectGoogle).toHaveBeenCalled());
    expect(assign).toHaveBeenCalledWith(
      "https://accounts.google.com/o/oauth2/v2/auth?x=1",
    );
  });

  it("renders connected account card and actions", async () => {
    fetchEmailAccounts.mockResolvedValue({ items: [mockAccount] });
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("hello@example.com")).toBeInTheDocument();
    });
    expect(screen.getByText("Connected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Test Connection/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Send Test Email/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Settings/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Disconnect/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Test Connection/i }));
    await waitFor(() => expect(testEmailAccountConnection).toHaveBeenCalledWith("acc-1"));
  });

  it("opens settings modal with validation", async () => {
    fetchEmailAccounts.mockResolvedValue({ items: [mockAccount] });
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("hello@example.com"));
    await user.click(screen.getByRole("button", { name: /Settings/i }));
    expect(screen.getByRole("heading", { name: /Account settings/i })).toBeInTheDocument();
    expect(
      screen.getByText(/safety limits configured inside MailFlow/i),
    ).toBeInTheDocument();
    const daily = screen.getByLabelText(/Daily send limit/i);
    await user.clear(daily);
    await user.type(daily, "5");
    const hourly = screen.getByLabelText(/Hourly send limit/i);
    await user.clear(hourly);
    await user.type(hourly, "20");
    await user.click(screen.getByRole("button", { name: /^Save$/i }));
    await waitFor(() => {
      expect(screen.getByText(/Hourly limit cannot exceed daily limit/i)).toBeInTheDocument();
    });
  });

  it("opens send test email modal including template mode", async () => {
    fetchEmailAccounts.mockResolvedValue({ items: [mockAccount] });
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("hello@example.com"));
    await user.click(screen.getByRole("button", { name: /Send Test Email/i }));
    expect(screen.getByRole("heading", { name: /Send test email/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Recipient email/i)).toBeInTheDocument();
    await user.click(screen.getByLabelText(/Existing template/i));
    await waitFor(() => {
      expect(screen.getByLabelText(/^Template$/i)).toBeInTheDocument();
    });
  });

  it("shows disconnect confirmation", async () => {
    fetchEmailAccounts.mockResolvedValue({ items: [mockAccount] });
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("hello@example.com"));
    await user.click(screen.getByRole("button", { name: /Disconnect/i }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/Disconnect Gmail account/i)).toBeInTheDocument();
    expect(within(dialog).getByText(/hello@example.com/)).toBeInTheDocument();
  });

  it("displays error status", async () => {
    fetchEmailAccounts.mockResolvedValue({
      items: [
        {
          ...mockAccount,
          connection_status: "error",
          last_connection_error: "Gmail API is temporarily unavailable. Try again shortly.",
        },
      ],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Error")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/Gmail API is temporarily unavailable/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Reconnect Gmail/i })).toBeInTheDocument();
  });
});
