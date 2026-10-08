import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/Toast";
import { CampaignDetailPage } from "@/features/campaigns/CampaignDetailPage";

const fetchCampaign = vi.fn();
const fetchCampaignStats = vi.fn();
const validateCampaign = vi.fn();
const previewCampaign = vi.fn();
const startCampaign = vi.fn();
const pauseCampaign = vi.fn();
const resumeCampaign = vi.fn();
const cancelCampaign = vi.fn();
const fetchCampaignMessages = vi.fn();

vi.mock("@/api/campaigns", () => ({
  fetchCampaign: (...a: unknown[]) => fetchCampaign(...a),
  fetchCampaignStats: (...a: unknown[]) => fetchCampaignStats(...a),
  validateCampaign: (...a: unknown[]) => validateCampaign(...a),
  previewCampaign: (...a: unknown[]) => previewCampaign(...a),
  startCampaign: (...a: unknown[]) => startCampaign(...a),
  pauseCampaign: (...a: unknown[]) => pauseCampaign(...a),
  resumeCampaign: (...a: unknown[]) => resumeCampaign(...a),
  cancelCampaign: (...a: unknown[]) => cancelCampaign(...a),
  fetchCampaignMessages: (...a: unknown[]) => fetchCampaignMessages(...a),
  deleteCampaign: vi.fn(),
  returnCampaignToDraft: vi.fn(),
}));

const readyCampaign = {
  id: "camp-1",
  name: "Chennai Business Outreach",
  description: null,
  status: "ready",
  email_account_id: "acc-1",
  template_id: "tpl-1",
  contact_list_id: "list-1",
  subject_override: null,
  html_override: null,
  plain_text_override: null,
  has_content_snapshot: true,
  snapshot_subject: "Hello",
  daily_limit: 80,
  hourly_limit: 10,
  minimum_delay_seconds: 30,
  maximum_delay_seconds: 90,
  stop_on_reply: true,
  skip_suppressed: true,
  ready_at: "2026-01-01T00:00:00Z",
  cancelled_at: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  email_account: {
    id: "acc-1",
    email_address: "hello@example.com",
    provider: "gmail",
    connection_status: "connected",
    daily_send_limit: 100,
    hourly_send_limit: 20,
    minimum_delay_seconds: 30,
    maximum_delay_seconds: 90,
    is_active: true,
  },
  effective_limits: {
    daily_limit: 80,
    hourly_limit: 10,
    minimum_delay_seconds: 30,
    maximum_delay_seconds: 90,
    inherited_from_account: true,
  },
  stats: { total: 10, eligible: 5, pending: 5, excluded: 0, invalid: 0, suppressed: 0, queued: 0, sent: 0, failed: 0, replied: 0 },
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter initialEntries={["/campaigns/camp-1"]}>
      <QueryClientProvider client={client}>
        <ToastProvider>
          <Routes>
            <Route path="/campaigns/:id" element={<CampaignDetailPage />} />
          </Routes>
        </ToastProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("CampaignDetailPage delivery UI", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchCampaign.mockResolvedValue(readyCampaign);
    validateCampaign.mockResolvedValue({
      valid: true,
      errors: [],
      warnings: [],
      eligible_recipients: 1240,
    });
    previewCampaign.mockResolvedValue({
      email: "a@example.com",
      rendered_subject: "Hi",
      rendered_html: "<p>Hi</p>",
    });
    fetchCampaignMessages.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 });
  });

  it("shows start button and confirmation for ready campaign", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByRole("button", { name: /start campaign/i })).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /start campaign/i }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog.textContent).toMatch(/Chennai Business Outreach/);
    expect(dialog.textContent).toMatch(/hello@example.com/);
    expect(dialog.textContent).toMatch(/1240/);
  });

  it("shows running progress and pause", async () => {
    fetchCampaign.mockResolvedValue({
      ...readyCampaign,
      status: "running",
      stats: {
        ...readyCampaign.stats,
        messages_total: 100,
        messages_sent: 40,
        messages_queued: 55,
        messages_failed: 5,
        progress_percent: 45,
      },
    });
    fetchCampaignStats.mockResolvedValue({
      messages_total: 100,
      messages_sent: 40,
      messages_queued: 55,
      messages_failed: 5,
      progress_percent: 45,
      eligible: 100,
      total: 100,
      pending: 0,
      excluded: 0,
      invalid: 0,
      suppressed: 0,
      queued: 55,
      sent: 40,
      failed: 5,
      replied: 0,
    });
    renderPage();
    await waitFor(() => expect(screen.getByText(/Delivery progress/)).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /^Pause$/i })).toBeInTheDocument();
  });

  it("shows messages tab with failed error label", async () => {
    fetchCampaign.mockResolvedValue({ ...readyCampaign, status: "completed" });
    fetchCampaignMessages.mockResolvedValue({
      items: [
        {
          id: "m1",
          to_email: "x@example.com",
          to_name: "X",
          status: "failed",
          attempt_count: 3,
          max_attempts: 3,
          sent_at: null,
          error_code: "AUTH_EXPIRED",
          error_message: "token bad",
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      total_pages: 1,
    });
    renderPage();
    await waitFor(() => screen.getByRole("button", { name: "Messages" }));
    await userEvent.click(screen.getByRole("button", { name: "Messages" }));
    await waitFor(() => expect(screen.getByText("Authentication expired")).toBeInTheDocument());
  });
});
