import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchEmailAccounts } from "@/api/emailAccounts";
import { fetchContactLists } from "@/api/contactLists";
import { fetchTemplates } from "@/api/templates";
import {
  createCampaign,
  fetchCampaign,
  markCampaignReady,
  previewCampaign,
  reviewCampaign,
  snapshotRecipients,
  updateCampaign,
  validateCampaign,
} from "@/api/campaigns";
import { PageHeader } from "@/components/PageHeader";
import { useToast } from "@/components/Toast";
import { CampaignStatusBadge } from "@/features/campaigns/CampaignStatusBadge";
import type { Campaign, CampaignPreview, RecipientSnapshotResponse } from "@/types/campaigns";
import { getErrorMessage } from "@/utils/errors";
import { cn } from "@/utils/cn";

const STEPS = [
  "Details",
  "Recipients",
  "Email Account",
  "Content",
  "Sending Settings",
  "Preview",
  "Review",
] as const;

function inferStep(campaign: Campaign): number {
  if (!campaign.name) return 0;
  if (!campaign.contact_list_id || !campaign.stats?.total) return 1;
  if (!campaign.email_account_id) return 2;
  if (!campaign.template_id && !campaign.html_override) return 3;
  if (campaign.daily_limit == null && campaign.hourly_limit == null) return 4;
  return 5;
}

export function CampaignWizardPage({ mode }: { mode: "new" | "edit" }) {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { pushToast } = useToast();
  const [step, setStep] = useState(0);
  const [hydrated, setHydrated] = useState(false);
  const [campaignId, setCampaignId] = useState<string | null>(mode === "edit" ? id || null : null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [listId, setListId] = useState("");
  const [snapshot, setSnapshot] = useState<RecipientSnapshotResponse | null>(null);
  const [accountId, setAccountId] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [contentMode, setContentMode] = useState<"template" | "custom">("template");
  const [subjectOverride, setSubjectOverride] = useState("");
  const [htmlOverride, setHtmlOverride] = useState("");
  const [dailyLimit, setDailyLimit] = useState("");
  const [hourlyLimit, setHourlyLimit] = useState("");
  const [minDelay, setMinDelay] = useState("");
  const [maxDelay, setMaxDelay] = useState("");
  const [stopOnReply, setStopOnReply] = useState(true);
  const [preview, setPreview] = useState<CampaignPreview | null>(null);
  const [previewTab, setPreviewTab] = useState<"html" | "text">("html");
  const [localError, setLocalError] = useState<string | null>(null);

  const campaignQuery = useQuery({
    queryKey: ["campaign", campaignId],
    queryFn: () => fetchCampaign(campaignId!),
    enabled: Boolean(campaignId),
  });

  const listsQuery = useQuery({ queryKey: ["contact-lists"], queryFn: fetchContactLists });
  const accountsQuery = useQuery({ queryKey: ["email-accounts"], queryFn: fetchEmailAccounts });
  const templatesQuery = useQuery({
    queryKey: ["templates", "wizard"],
    queryFn: () =>
      fetchTemplates({
        page: 1,
        page_size: 100,
        search: "",
        sort_by: "updated_at",
        sort_order: "desc",
      }),
  });
  const reviewQuery = useQuery({
    queryKey: ["campaign-review", campaignId],
    queryFn: () => reviewCampaign(campaignId!),
    enabled: Boolean(campaignId) && step === 6,
  });

  useEffect(() => {
    const c = campaignQuery.data;
    if (!c || hydrated) return;
    setName(c.name);
    setDescription(c.description || "");
    setListId(c.contact_list_id || "");
    setAccountId(c.email_account_id || "");
    setTemplateId(c.template_id || "");
    setSubjectOverride(c.subject_override || "");
    setHtmlOverride(c.html_override || "");
    setContentMode(c.html_override ? "custom" : "template");
    setDailyLimit(c.daily_limit != null ? String(c.daily_limit) : "");
    setHourlyLimit(c.hourly_limit != null ? String(c.hourly_limit) : "");
    setMinDelay(c.minimum_delay_seconds != null ? String(c.minimum_delay_seconds) : "");
    setMaxDelay(c.maximum_delay_seconds != null ? String(c.maximum_delay_seconds) : "");
    setStopOnReply(c.stop_on_reply);
    if (c.stats) {
      setSnapshot({
        contact_list_id: c.contact_list_id || "",
        total: c.stats.total,
        eligible: c.stats.eligible,
        invalid: c.stats.invalid,
        suppressed: c.stats.suppressed,
        excluded: c.stats.excluded,
        stats: c.stats,
      });
    }
    if (mode === "edit") {
      const resume = (location.state as { resumeStep?: number } | null)?.resumeStep;
      setStep(typeof resume === "number" ? resume : inferStep(c));
    }
    setHydrated(true);
  }, [campaignQuery.data, mode, hydrated, location.state]);

  const connectedAccounts = useMemo(
    () =>
      (accountsQuery.data?.items ?? []).filter(
        (a) => a.connection_status === "connected" && a.is_active,
      ),
    [accountsQuery.data],
  );

  const selectedAccount = connectedAccounts.find((a) => a.id === accountId);

  const saveDetails = useMutation({
    mutationFn: async () => {
      if (!name.trim()) throw new Error("Campaign name is required");
      if (campaignId) {
        return updateCampaign(campaignId, {
          name: name.trim(),
          description: description.trim() || null,
        });
      }
      return createCampaign({ name: name.trim(), description: description.trim() || null });
    },
    onSuccess: (c) => {
      setCampaignId(c.id);
      setLocalError(null);
      void queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      void queryClient.invalidateQueries({ queryKey: ["campaign", c.id] });
      setStep(1);
      if (mode === "new") {
        navigate(`/campaigns/${c.id}/edit`, { replace: true, state: { resumeStep: 1 } });
      }
    },
    onError: (e) => setLocalError(getErrorMessage(e)),
  });

  const saveSnapshot = useMutation({
    mutationFn: async () => {
      if (!campaignId) throw new Error("Save details first");
      if (!listId) throw new Error("Select a contact list");
      return snapshotRecipients(campaignId, listId);
    },
    onSuccess: (data) => {
      setSnapshot(data);
      setLocalError(null);
      pushToast("Recipients snapshotted");
      void queryClient.invalidateQueries({ queryKey: ["campaign", campaignId] });
      setStep(2);
    },
    onError: (e) => setLocalError(getErrorMessage(e)),
  });

  const saveAccount = useMutation({
    mutationFn: async () => {
      if (!campaignId || !accountId) throw new Error("Select an email account");
      return updateCampaign(campaignId, { email_account_id: accountId });
    },
    onSuccess: () => {
      setLocalError(null);
      void queryClient.invalidateQueries({ queryKey: ["campaign", campaignId] });
      setStep(3);
    },
    onError: (e) => setLocalError(getErrorMessage(e)),
  });

  const saveContent = useMutation({
    mutationFn: async () => {
      if (!campaignId) throw new Error("Missing campaign");
      if (contentMode === "template") {
        if (!templateId) throw new Error("Select a template");
        return updateCampaign(campaignId, {
          template_id: templateId,
          clear_overrides: true,
        });
      }
      if (!subjectOverride.trim() || !htmlOverride.trim()) {
        throw new Error("Subject and HTML content are required for custom content");
      }
      return updateCampaign(campaignId, {
        template_id: templateId || undefined,
        subject_override: subjectOverride.trim(),
        html_override: htmlOverride,
        use_custom_content: true,
      });
    },
    onSuccess: () => {
      setLocalError(null);
      void queryClient.invalidateQueries({ queryKey: ["campaign", campaignId] });
      setStep(4);
    },
    onError: (e) => setLocalError(getErrorMessage(e)),
  });

  const saveSettings = useMutation({
    mutationFn: async () => {
      if (!campaignId) throw new Error("Missing campaign");
      const payload: Parameters<typeof updateCampaign>[1] = {
        stop_on_reply: stopOnReply,
      };
      if (dailyLimit) payload.daily_limit = Number(dailyLimit);
      if (hourlyLimit) payload.hourly_limit = Number(hourlyLimit);
      if (minDelay) payload.minimum_delay_seconds = Number(minDelay);
      if (maxDelay) payload.maximum_delay_seconds = Number(maxDelay);
      if (
        payload.daily_limit != null &&
        payload.hourly_limit != null &&
        payload.hourly_limit > payload.daily_limit
      ) {
        throw new Error("Hourly limit cannot exceed daily limit");
      }
      return updateCampaign(campaignId, payload);
    },
    onSuccess: async () => {
      setLocalError(null);
      void queryClient.invalidateQueries({ queryKey: ["campaign", campaignId] });
      if (campaignId) {
        const p = await previewCampaign(campaignId);
        setPreview(p);
      }
      setStep(5);
    },
    onError: (e) => setLocalError(getErrorMessage(e)),
  });

  const readyMutation = useMutation({
    mutationFn: async () => {
      if (!campaignId) throw new Error("Missing campaign");
      const v = await validateCampaign(campaignId);
      if (!v.valid) throw new Error(v.errors.join("; ") || "Validation failed");
      return markCampaignReady(campaignId);
    },
    onSuccess: (c) => {
      pushToast("Campaign marked ready. No emails will be sent yet.");
      void queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      navigate(`/campaigns/${c.id}`);
    },
    onError: (e) => setLocalError(getErrorMessage(e)),
  });

  const loadPreview = async (contactId?: string | null) => {
    if (!campaignId) return;
    try {
      const p = await previewCampaign(campaignId, contactId);
      setPreview(p);
      setLocalError(null);
    } catch (e) {
      setLocalError(getErrorMessage(e));
    }
  };

  if (mode === "edit" && campaignQuery.isLoading) {
    return <p className="text-sm text-ink-muted">Loading campaign…</p>;
  }

  return (
    <div>
      <PageHeader
        title={mode === "new" ? "New Campaign" : name || "Edit Campaign"}
        description="Plan recipients, content, and limits. Marking ready does not send email."
        actions={
          campaignQuery.data ? <CampaignStatusBadge status={campaignQuery.data.status} /> : null
        }
      />

      <ol className="mb-6 flex flex-wrap gap-2">
        {STEPS.map((label, index) => (
          <li key={label}>
            <button
              type="button"
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-medium ring-1 ring-inset",
                index === step
                  ? "bg-brand text-white ring-brand"
                  : index < step
                    ? "bg-emerald-50 text-emerald-800 ring-emerald-600/20"
                    : "bg-surface-muted text-ink-muted ring-surface-border",
              )}
              onClick={() => campaignId && index <= step && setStep(index)}
            >
              {index + 1}. {label}
            </button>
          </li>
        ))}
      </ol>

      {localError ? <p className="mb-4 text-sm text-red-600">{localError}</p> : null}

      <div className="card p-5">
        {step === 0 && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-ink">Campaign details</h2>
            <div>
              <label className="mb-1 block text-sm font-medium" htmlFor="camp-name">
                Campaign name
              </label>
              <input
                id="camp-name"
                className="input"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium" htmlFor="camp-desc">
                Description (optional)
              </label>
              <textarea
                id="camp-desc"
                className="input min-h-[80px]"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <button
              type="button"
              className="btn-primary"
              disabled={saveDetails.isPending}
              onClick={() => saveDetails.mutate()}
            >
              {saveDetails.isPending ? "Saving…" : "Save & Continue"}
            </button>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-ink">Recipients</h2>
            <p className="text-sm text-ink-muted">
              Snapshots freeze the audience. Later contact-list changes will not alter this campaign.
            </p>
            <div>
              <label className="mb-1 block text-sm font-medium" htmlFor="camp-list">
                Contact list
              </label>
              <select
                id="camp-list"
                className="input"
                value={listId}
                onChange={(e) => {
                  setListId(e.target.value);
                  setSnapshot(null);
                }}
              >
                <option value="">Select list…</option>
                {(listsQuery.data ?? []).map((list) => (
                  <option key={list.id} value={list.id}>
                    {list.name} ({list.total_contacts} contacts)
                  </option>
                ))}
              </select>
            </div>
            {snapshot ? (
              <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                {[
                  ["Total", snapshot.total],
                  ["Eligible", snapshot.eligible],
                  ["Invalid", snapshot.invalid],
                  ["Suppressed", snapshot.suppressed],
                  ["Excluded", snapshot.excluded],
                ].map(([label, value]) => (
                  <div key={String(label)} className="rounded-lg bg-surface-muted p-3">
                    <dt className="text-xs text-ink-subtle">{label}</dt>
                    <dd className="text-lg font-semibold text-ink">{value}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-secondary" onClick={() => setStep(0)}>
                Back
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={saveSnapshot.isPending || !listId}
                onClick={() => saveSnapshot.mutate()}
              >
                {saveSnapshot.isPending ? "Analyzing…" : "Use These Recipients"}
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-ink">Email account</h2>
            {connectedAccounts.length === 0 ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                No connected Gmail accounts.{" "}
                <Link to="/email-accounts" className="font-medium underline">
                  Connect Gmail
                </Link>
              </div>
            ) : (
              <div className="grid gap-3">
                {connectedAccounts.map((account) => (
                  <label
                    key={account.id}
                    className={cn(
                      "flex cursor-pointer items-start gap-3 rounded-lg border p-4",
                      accountId === account.id
                        ? "border-brand bg-brand/5"
                        : "border-surface-border",
                    )}
                  >
                    <input
                      type="radio"
                      name="account"
                      checked={accountId === account.id}
                      onChange={() => setAccountId(account.id)}
                    />
                    <span>
                      <span className="block font-medium text-ink">{account.email_address}</span>
                      <span className="text-xs text-ink-muted">
                        {account.provider} · {account.daily_send_limit}/day ·{" "}
                        {account.hourly_send_limit}/hour
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-secondary" onClick={() => setStep(1)}>
                Back
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={saveAccount.isPending || !accountId}
                onClick={() => saveAccount.mutate()}
              >
                Save & Continue
              </button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-ink">Content</h2>
            <fieldset>
              <legend className="mb-2 text-sm font-medium">Source</legend>
              <div className="flex gap-4">
                <label className="inline-flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    checked={contentMode === "template"}
                    onChange={() => setContentMode("template")}
                  />
                  Use existing template
                </label>
                <label className="inline-flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    checked={contentMode === "custom"}
                    onChange={() => setContentMode("custom")}
                  />
                  Custom content
                </label>
              </div>
            </fieldset>
            <div>
              <label className="mb-1 block text-sm font-medium" htmlFor="camp-template">
                Template
              </label>
              <select
                id="camp-template"
                className="input"
                value={templateId}
                onChange={(e) => {
                  setTemplateId(e.target.value);
                  const t = templatesQuery.data?.items.find((x) => x.id === e.target.value);
                  if (t && contentMode === "custom") {
                    setSubjectOverride(t.subject);
                    setHtmlOverride(t.html_content);
                  }
                }}
              >
                <option value="">Select template…</option>
                {(templatesQuery.data?.items ?? []).map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
            {contentMode === "custom" ? (
              <>
                <div>
                  <label className="mb-1 block text-sm font-medium" htmlFor="camp-subject">
                    Subject
                  </label>
                  <input
                    id="camp-subject"
                    className="input"
                    value={subjectOverride}
                    onChange={(e) => setSubjectOverride(e.target.value)}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium" htmlFor="camp-html">
                    HTML content
                  </label>
                  <textarea
                    id="camp-html"
                    className="input min-h-[160px] font-mono text-xs"
                    value={htmlOverride}
                    onChange={(e) => setHtmlOverride(e.target.value)}
                  />
                  <p className="mt-1 text-xs text-ink-muted">
                    Customizes this campaign only — the original template is not modified.
                  </p>
                </div>
              </>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-secondary" onClick={() => setStep(2)}>
                Back
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={saveContent.isPending}
                onClick={() => saveContent.mutate()}
              >
                Save & Continue
              </button>
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-ink">Sending settings</h2>
            {selectedAccount ? (
              <p className="text-sm text-ink-muted">
                Account max: {selectedAccount.daily_send_limit}/day ·{" "}
                {selectedAccount.hourly_send_limit}/hour · delays{" "}
                {selectedAccount.minimum_delay_seconds}–
                {selectedAccount.maximum_delay_seconds}s. Leave blank to inherit.
              </p>
            ) : null}
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium" htmlFor="daily">
                  Daily limit
                </label>
                <input
                  id="daily"
                  type="number"
                  className="input"
                  value={dailyLimit}
                  onChange={(e) => setDailyLimit(e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium" htmlFor="hourly">
                  Hourly limit
                </label>
                <input
                  id="hourly"
                  type="number"
                  className="input"
                  value={hourlyLimit}
                  onChange={(e) => setHourlyLimit(e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium" htmlFor="min-delay">
                  Minimum delay (seconds)
                </label>
                <input
                  id="min-delay"
                  type="number"
                  className="input"
                  value={minDelay}
                  onChange={(e) => setMinDelay(e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium" htmlFor="max-delay">
                  Maximum delay (seconds)
                </label>
                <input
                  id="max-delay"
                  type="number"
                  className="input"
                  value={maxDelay}
                  onChange={(e) => setMaxDelay(e.target.value)}
                />
              </div>
            </div>
            <label className="inline-flex items-center gap-2 text-sm text-ink">
              <input
                type="checkbox"
                checked={stopOnReply}
                onChange={(e) => setStopOnReply(e.target.checked)}
              />
              Stop on reply (future sending will stop after a detected reply)
            </label>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-secondary" onClick={() => setStep(3)}>
                Back
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={saveSettings.isPending}
                onClick={() => saveSettings.mutate()}
              >
                Save & Continue
              </button>
            </div>
          </div>
        )}

        {step === 5 && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-ink">Preview</h2>
            {preview ? (
              <>
                <p className="text-sm text-ink-muted">
                  To:{" "}
                  <span className="font-medium text-ink">
                    {[preview.first_name, preview.last_name].filter(Boolean).join(" ") || "—"}
                    {` <${preview.email}>`}
                  </span>{" "}
                  ({preview.position} of {preview.total_eligible})
                </p>
                <p className="text-sm font-medium text-ink">Subject: {preview.rendered_subject}</p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    className={cn("btn-secondary text-xs", previewTab === "html" && "ring-brand")}
                    onClick={() => setPreviewTab("html")}
                  >
                    HTML
                  </button>
                  <button
                    type="button"
                    className={cn("btn-secondary text-xs", previewTab === "text" && "ring-brand")}
                    onClick={() => setPreviewTab("text")}
                  >
                    Plain text
                  </button>
                </div>
                {previewTab === "html" ? (
                  <div
                    className="prose prose-sm max-w-none rounded-lg border border-surface-border p-4"
                    dangerouslySetInnerHTML={{ __html: preview.rendered_html }}
                  />
                ) : (
                  <pre className="whitespace-pre-wrap rounded-lg border border-surface-border bg-surface-muted p-4 text-sm">
                    {preview.rendered_text}
                  </pre>
                )}
                {preview.warnings.length ? (
                  <ul className="list-disc pl-5 text-sm text-amber-800">
                    {preview.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                ) : null}
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="btn-secondary"
                    disabled={!preview.has_previous}
                    onClick={() => void loadPreview(preview.previous_contact_id)}
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    className="btn-secondary"
                    disabled={!preview.has_next}
                    onClick={() => void loadPreview(preview.next_contact_id)}
                  >
                    Next
                  </button>
                </div>
              </>
            ) : (
              <p className="text-sm text-ink-muted">Loading preview…</p>
            )}
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-secondary" onClick={() => setStep(4)}>
                Back
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={() => {
                  void queryClient.invalidateQueries({ queryKey: ["campaign-review", campaignId] });
                  setStep(6);
                }}
              >
                Continue to Review
              </button>
            </div>
          </div>
        )}

        {step === 6 && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-ink">Review</h2>
            <div className="rounded-lg border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900">
              No emails will be sent yet. Marking ready only freezes this plan for Phase 7.
            </div>
            {reviewQuery.data ? (
              <>
                <dl className="grid gap-2 text-sm sm:grid-cols-2">
                  <div>
                    <dt className="text-ink-subtle">Campaign</dt>
                    <dd className="font-medium">{reviewQuery.data.campaign.name}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-subtle">Email account</dt>
                    <dd className="font-medium">
                      {reviewQuery.data.campaign.email_account?.email_address ?? "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-ink-subtle">Content</dt>
                    <dd className="font-medium">
                      {reviewQuery.data.campaign.template?.name ||
                        reviewQuery.data.campaign.content_source ||
                        "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-ink-subtle">Eligible recipients</dt>
                    <dd className="font-medium">
                      {reviewQuery.data.campaign.stats?.eligible ?? 0} /{" "}
                      {reviewQuery.data.campaign.stats?.total ?? 0}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-ink-subtle">Limits</dt>
                    <dd className="font-medium">
                      {reviewQuery.data.campaign.effective_limits
                        ? `${reviewQuery.data.campaign.effective_limits.daily_limit}/day · ${reviewQuery.data.campaign.effective_limits.hourly_limit}/hour`
                        : "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-ink-subtle">Stop on reply</dt>
                    <dd className="font-medium">
                      {reviewQuery.data.campaign.stop_on_reply ? "Yes" : "No"}
                    </dd>
                  </div>
                </dl>
                {reviewQuery.data.validation.errors.length ? (
                  <ul className="list-disc pl-5 text-sm text-red-700">
                    {reviewQuery.data.validation.errors.map((e) => (
                      <li key={e}>{e}</li>
                    ))}
                  </ul>
                ) : null}
                {reviewQuery.data.validation.warnings.length ? (
                  <ul className="list-disc pl-5 text-sm text-amber-800">
                    {reviewQuery.data.validation.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                ) : null}
              </>
            ) : (
              <p className="text-sm text-ink-muted">Loading review…</p>
            )}
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-secondary" onClick={() => setStep(5)}>
                Back
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={
                  readyMutation.isPending ||
                  (reviewQuery.data ? !reviewQuery.data.validation.valid : true)
                }
                onClick={() => readyMutation.mutate()}
              >
                {readyMutation.isPending ? "Marking ready…" : "Mark Campaign Ready"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
