import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/Toast";
import { CampaignListPage } from "@/features/campaigns/CampaignListPage";
import type { Campaign } from "@/types/campaigns";

const fetchCampaigns = vi.fn();
const deleteCampaign = vi.fn();
const cancelCampaign = vi.fn();

vi.mock("@/api/campaigns", () => ({
  fetchCampaigns: (...args: unknown[]) => fetchCampaigns(...args),
  deleteCampaign: (...args: unknown[]) => deleteCampaign(...args),
  cancelCampaign: (...args: unknown[]) => cancelCampaign(...args),
}));

const draft: Campaign = {
  id: "c1",
  name: "Q4 Outreach",
  description: null,
  status: "draft",
  email_account_id: null,
  template_id: null,
  contact_list_id: null,
  subject_override: null,
  html_override: null,
  plain_text_override: null,
  has_content_snapshot: false,
  snapshot_subject: null,
  daily_limit: null,
  hourly_limit: null,
  minimum_delay_seconds: null,
  maximum_delay_seconds: null,
  stop_on_reply: true,
  skip_suppressed: true,
  ready_at: null,
  cancelled_at: null,
  created_at: "2026-10-07T10:00:00Z",
  updated_at: "2026-10-07T10:00:00Z",
  stats: {
    total: 10,
    eligible: 8,
    pending: 8,
    excluded: 0,
    invalid: 1,
    suppressed: 1,
    queued: 0,
    sent: 0,
    failed: 0,
    replied: 0,
  },
  email_account: {
    id: "a1",
    email_address: "hello@example.com",
    provider: "gmail",
    connection_status: "connected",
    daily_send_limit: 100,
    hourly_send_limit: 20,
    minimum_delay_seconds: 30,
    maximum_delay_seconds: 90,
    is_active: true,
  },
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <ToastProvider>
          <CampaignListPage />
        </ToastProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("CampaignListPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchCampaigns.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 25,
      total: 0,
      total_pages: 0,
    });
  });

  it("renders heading and empty state with new campaign CTA", async () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Campaigns" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/No campaigns yet/i)).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: /New Campaign/i })).toHaveAttribute(
      "href",
      "/campaigns/new",
    );
    expect(screen.getByRole("link", { name: /Create your first campaign/i })).toBeInTheDocument();
  });

  it("renders campaign row with status and actions", async () => {
    fetchCampaigns.mockResolvedValue({
      items: [draft],
      page: 1,
      page_size: 25,
      total: 1,
      total_pages: 1,
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Q4 Outreach")).toBeInTheDocument();
    });
    expect(screen.getAllByText("Draft").length).toBeGreaterThan(0);
    expect(screen.getByText(/8 eligible/i)).toBeInTheDocument();
    expect(screen.getByText("hello@example.com")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^Edit$/i })).toHaveAttribute(
      "href",
      "/campaigns/c1/edit",
    );
  });

  it("shows cancelled status", async () => {
    fetchCampaigns.mockResolvedValue({
      items: [{ ...draft, status: "cancelled", name: "Old" }],
      page: 1,
      page_size: 25,
      total: 1,
      total_pages: 1,
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Cancelled")).toBeInTheDocument());
  });

  it("opens delete confirmation for draft", async () => {
    fetchCampaigns.mockResolvedValue({
      items: [draft],
      page: 1,
      page_size: 25,
      total: 1,
      total_pages: 1,
    });
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("Q4 Outreach"));
    await user.click(screen.getByRole("button", { name: /Delete/i }));
    expect(screen.getByRole("heading", { name: /Delete draft campaign/i })).toBeInTheDocument();
  });
});
