import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/Toast";
import { CampaignWizardPage } from "@/features/campaigns/CampaignWizardPage";

const createCampaign = vi.fn();
const updateCampaign = vi.fn();
const fetchCampaign = vi.fn();
const snapshotRecipients = vi.fn();
const previewCampaign = vi.fn();
const reviewCampaign = vi.fn();
const validateCampaign = vi.fn();
const markCampaignReady = vi.fn();
const fetchContactLists = vi.fn();
const fetchEmailAccounts = vi.fn();
const fetchTemplates = vi.fn();

vi.mock("@/api/campaigns", () => ({
  createCampaign: (...a: unknown[]) => createCampaign(...a),
  updateCampaign: (...a: unknown[]) => updateCampaign(...a),
  fetchCampaign: (...a: unknown[]) => fetchCampaign(...a),
  snapshotRecipients: (...a: unknown[]) => snapshotRecipients(...a),
  previewCampaign: (...a: unknown[]) => previewCampaign(...a),
  reviewCampaign: (...a: unknown[]) => reviewCampaign(...a),
  validateCampaign: (...a: unknown[]) => validateCampaign(...a),
  markCampaignReady: (...a: unknown[]) => markCampaignReady(...a),
}));

vi.mock("@/api/contactLists", () => ({
  fetchContactLists: (...a: unknown[]) => fetchContactLists(...a),
}));

vi.mock("@/api/emailAccounts", () => ({
  fetchEmailAccounts: (...a: unknown[]) => fetchEmailAccounts(...a),
}));

vi.mock("@/api/templates", () => ({
  fetchTemplates: (...a: unknown[]) => fetchTemplates(...a),
}));

function renderWizard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter initialEntries={["/campaigns/new"]}>
      <QueryClientProvider client={client}>
        <ToastProvider>
          <Routes>
            <Route path="/campaigns/new" element={<CampaignWizardPage mode="new" />} />
            <Route path="/campaigns/:id/edit" element={<CampaignWizardPage mode="edit" />} />
          </Routes>
        </ToastProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("CampaignWizardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchContactLists.mockResolvedValue([
      { id: "l1", name: "Locals", total_contacts: 12, description: null },
    ]);
    fetchEmailAccounts.mockResolvedValue({
      items: [
        {
          id: "a1",
          email_address: "me@gmail.com",
          provider: "gmail",
          connection_status: "connected",
          daily_send_limit: 100,
          hourly_send_limit: 20,
          minimum_delay_seconds: 30,
          maximum_delay_seconds: 90,
          is_active: true,
        },
      ],
    });
    fetchTemplates.mockResolvedValue({
      items: [{ id: "t1", name: "Welcome", subject: "Hi {{first_name}}" }],
      page: 1,
      page_size: 100,
      total: 1,
      total_pages: 1,
    });
    createCampaign.mockResolvedValue({
      id: "c1",
      name: "Test Campaign",
      status: "draft",
      description: null,
      email_account_id: null,
      template_id: null,
      contact_list_id: null,
      stats: null,
    });
    updateCampaign.mockResolvedValue({ id: "c1", name: "Test Campaign", status: "draft" });
    fetchCampaign.mockResolvedValue({
      id: "c1",
      name: "Test Campaign",
      status: "draft",
      description: null,
      email_account_id: null,
      template_id: null,
      contact_list_id: null,
      subject_override: null,
      html_override: null,
      stop_on_reply: true,
      stats: null,
    });
    snapshotRecipients.mockResolvedValue({
      contact_list_id: "l1",
      total: 12,
      eligible: 10,
      invalid: 1,
      suppressed: 1,
      excluded: 0,
      stats: {
        total: 12,
        eligible: 10,
        pending: 10,
        excluded: 0,
        invalid: 1,
        suppressed: 1,
        queued: 0,
        sent: 0,
        failed: 0,
        replied: 0,
      },
    });
    previewCampaign.mockResolvedValue({
      contact_id: "ct1",
      email: "arun@example.com",
      first_name: "Arun",
      last_name: "Kumar",
      company: "ABC",
      rendered_subject: "Hi Arun",
      rendered_html: "<p>Hello Arun</p>",
      rendered_text: "Hello Arun",
      warnings: [],
      has_previous: false,
      has_next: true,
      previous_contact_id: null,
      next_contact_id: "ct2",
      position: 1,
      total_eligible: 10,
    });
    reviewCampaign.mockResolvedValue({
      campaign: {
        id: "c1",
        name: "Test Campaign",
        status: "draft",
        stop_on_reply: true,
        email_account: { email_address: "me@gmail.com" },
        template: { name: "Welcome" },
        stats: { eligible: 10, total: 12 },
        effective_limits: { daily_limit: 80, hourly_limit: 15 },
      },
      validation: { valid: true, errors: [], warnings: [], eligible_recipients: 10 },
      message: "No emails will be sent yet.",
    });
    validateCampaign.mockResolvedValue({
      valid: true,
      errors: [],
      warnings: [],
      eligible_recipients: 10,
    });
    markCampaignReady.mockResolvedValue({ id: "c1", status: "ready" });
  });

  it("opens wizard details step and validates name", async () => {
    const user = userEvent.setup();
    renderWizard();
    expect(screen.getByRole("heading", { name: /New Campaign/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Campaign name/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Save & Continue/i }));
    await waitFor(() => {
      expect(screen.getByText(/Campaign name is required/i)).toBeInTheDocument();
    });
  });

  it("saves details and advances to recipients", async () => {
    const user = userEvent.setup();
    renderWizard();
    await user.type(screen.getByLabelText(/Campaign name/i), "Test Campaign");
    await user.click(screen.getByRole("button", { name: /Save & Continue/i }));
    await waitFor(() => expect(createCampaign).toHaveBeenCalled());
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Recipients/i })).toBeInTheDocument();
    });
  });
});
