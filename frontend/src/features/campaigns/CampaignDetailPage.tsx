import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cancelCampaign,
  deleteCampaign,
  fetchCampaign,
  fetchCampaignMessages,
  fetchCampaignStats,
  pauseCampaign,
  previewCampaign,
  resumeCampaign,
  returnCampaignToDraft,
  startCampaign,
  validateCampaign,
} from "@/api/campaigns";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PageHeader } from "@/components/PageHeader";
import { useToast } from "@/components/Toast";
import { CampaignStatusBadge } from "@/features/campaigns/CampaignStatusBadge";
import { formatMessageError } from "@/features/campaigns/messageErrors";
import { getErrorMessage } from "@/utils/errors";
import { useMemo, useState } from "react";

type TabId = "overview" | "messages";

const MESSAGE_FILTERS = ["", "queued", "sending", "sent", "failed", "cancelled"] as const;

export function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { pushToast } = useToast();
  const [tab, setTab] = useState<TabId>("overview");
  const [cancelOpen, setCancelOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [startOpen, setStartOpen] = useState(false);
  const [messageStatus, setMessageStatus] = useState<string>("");
  const [messagePage, setMessagePage] = useState(1);

  const campaignQuery = useQuery({
    queryKey: ["campaign", id],
    queryFn: () => fetchCampaign(id!),
    enabled: Boolean(id),
  });

  const campaign = campaignQuery.data;
  const pollStats =
    campaign?.status === "running" || campaign?.status === "paused";

  const statsQuery = useQuery({
    queryKey: ["campaign-stats", id],
    queryFn: () => fetchCampaignStats(id!),
    enabled: Boolean(id) && pollStats,
    refetchInterval: pollStats ? 8000 : false,
  });

  const stats = pollStats ? statsQuery.data ?? campaign?.stats : campaign?.stats;

  const validationQuery = useQuery({
    queryKey: ["campaign-validate", id],
    queryFn: () => validateCampaign(id!),
    enabled: Boolean(id),
  });

  const previewQuery = useQuery({
    queryKey: ["campaign-preview", id],
    queryFn: () => previewCampaign(id!),
    enabled: Boolean(id) && (campaign?.stats?.eligible ?? 0) > 0,
  });

  const messagesQuery = useQuery({
    queryKey: ["campaign-messages", id, messagePage, messageStatus],
    queryFn: () =>
      fetchCampaignMessages(id!, {
        page: messagePage,
        page_size: 20,
        status: messageStatus || undefined,
      }),
    enabled: Boolean(id) && tab === "messages",
    refetchInterval: pollStats ? 8000 : false,
  });

  const invalidateCampaign = async () => {
    await queryClient.invalidateQueries({ queryKey: ["campaign", id] });
    await queryClient.invalidateQueries({ queryKey: ["campaign-stats", id] });
    await queryClient.invalidateQueries({ queryKey: ["campaign-messages", id] });
    await queryClient.invalidateQueries({ queryKey: ["campaigns"] });
  };

  const startMutation = useMutation({
    mutationFn: () => startCampaign(id!),
    onSuccess: async () => {
      setStartOpen(false);
      pushToast("Campaign started");
      await invalidateCampaign();
    },
    onError: (e) => pushToast(getErrorMessage(e), "error"),
  });

  const pauseMutation = useMutation({
    mutationFn: () => pauseCampaign(id!),
    onSuccess: async () => {
      pushToast("Campaign paused");
      await invalidateCampaign();
    },
    onError: (e) => pushToast(getErrorMessage(e), "error"),
  });

  const resumeMutation = useMutation({
    mutationFn: () => resumeCampaign(id!),
    onSuccess: async () => {
      pushToast("Campaign resumed");
      await invalidateCampaign();
    },
    onError: (e) => pushToast(getErrorMessage(e), "error"),
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelCampaign(id!),
    onSuccess: async () => {
      setCancelOpen(false);
      pushToast("Campaign cancelled");
      await invalidateCampaign();
    },
    onError: (e) => pushToast(getErrorMessage(e), "error"),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteCampaign(id!),
    onSuccess: async () => {
      pushToast("Draft deleted");
      await queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      navigate("/campaigns");
    },
    onError: (e) => pushToast(getErrorMessage(e), "error"),
  });

  const editMutation = useMutation({
    mutationFn: () => returnCampaignToDraft(id!),
    onSuccess: async () => {
      pushToast("Returned to draft");
      await queryClient.invalidateQueries({ queryKey: ["campaign", id] });
      navigate(`/campaigns/${id}/edit`);
    },
    onError: (e) => pushToast(getErrorMessage(e), "error"),
  });

  const progress = useMemo(() => {
    const total = stats?.messages_total ?? stats?.eligible ?? 0;
    const processed =
      (stats?.messages_sent ?? stats?.sent ?? 0) +
      (stats?.messages_failed ?? stats?.failed ?? 0) +
      (stats?.messages_cancelled ?? stats?.cancelled ?? 0);
    const pct = stats?.progress_percent ?? (total ? Math.min(100, (processed / total) * 100) : 0);
    return { total, processed, pct };
  }, [stats]);

  if (campaignQuery.isLoading) {
    return <p className="text-sm text-ink-muted">Loading campaign…</p>;
  }
  if (!campaign) {
    return <p className="text-sm text-red-600">Campaign not found.</p>;
  }

  return (
    <div>
      <PageHeader
        title={campaign.name}
        description={campaign.description || undefined}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <CampaignStatusBadge status={campaign.status} />
            {campaign.status === "draft" ? (
              <>
                <Link to={`/campaigns/${campaign.id}/edit`} className="btn-primary">
                  Edit
                </Link>
                <button
                  type="button"
                  className="btn-secondary text-red-700"
                  onClick={() => setDeleteOpen(true)}
                >
                  Delete
                </button>
              </>
            ) : null}
            {campaign.status === "ready" ? (
              <>
                <button type="button" className="btn-primary" onClick={() => setStartOpen(true)}>
                  Start campaign
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => editMutation.mutate()}
                  disabled={editMutation.isPending}
                >
                  Return to draft
                </button>
                <button
                  type="button"
                  className="btn-secondary text-red-700"
                  onClick={() => setCancelOpen(true)}
                >
                  Cancel
                </button>
              </>
            ) : null}
            {campaign.status === "running" ? (
              <>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => pauseMutation.mutate()}
                  disabled={pauseMutation.isPending}
                >
                  Pause
                </button>
                <button
                  type="button"
                  className="btn-secondary text-red-700"
                  onClick={() => setCancelOpen(true)}
                >
                  Cancel
                </button>
              </>
            ) : null}
            {campaign.status === "paused" ? (
              <>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => resumeMutation.mutate()}
                  disabled={resumeMutation.isPending}
                >
                  Resume
                </button>
                <button
                  type="button"
                  className="btn-secondary text-red-700"
                  onClick={() => setCancelOpen(true)}
                >
                  Cancel
                </button>
              </>
            ) : null}
          </div>
        }
      />

      {campaign.status === "ready" ? (
        <div className="mb-6 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
          Campaign is ready to send. Review limits and recipients, then start when you are ready.
        </div>
      ) : null}

      {campaign.status === "paused" ? (
        <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          Campaign paused. No new messages will be sent until you resume it.
        </div>
      ) : null}

      {campaign.status === "completed" ? (
        <div className="mb-6 rounded-lg border border-indigo-200 bg-indigo-50 p-4 text-sm text-indigo-900">
          Campaign completed. Sent: {stats?.messages_sent ?? stats?.sent ?? 0} · Failed:{" "}
          {stats?.messages_failed ?? stats?.failed ?? 0} · Cancelled/skipped:{" "}
          {stats?.messages_cancelled ?? stats?.cancelled ?? 0}. Reply tracking will be added in a
          later phase.
        </div>
      ) : null}

      {campaign.status === "cancelled" ? (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          This campaign was cancelled. Recipient and message history was retained.
        </div>
      ) : null}

      {(campaign.status === "running" || campaign.status === "paused") && (
        <section className="card mb-6 space-y-3 p-5">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <h2 className="text-base font-semibold text-ink">Delivery progress</h2>
            <p className="text-sm text-ink-muted">
              {progress.processed} / {progress.total} processed
            </p>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-surface-border">
            <div
              className="h-full rounded-full bg-sky-600 transition-all"
              style={{ width: `${progress.pct}%` }}
            />
          </div>
          <div className="grid gap-3 text-sm sm:grid-cols-4">
            <div>
              <span className="text-ink-subtle">Sent</span>
              <p className="font-semibold">{stats?.messages_sent ?? stats?.sent ?? 0}</p>
            </div>
            <div>
              <span className="text-ink-subtle">Queued</span>
              <p className="font-semibold">{stats?.messages_queued ?? stats?.queued ?? 0}</p>
            </div>
            <div>
              <span className="text-ink-subtle">Sending</span>
              <p className="font-semibold">{stats?.messages_sending ?? stats?.sending ?? 0}</p>
            </div>
            <div>
              <span className="text-ink-subtle">Failed</span>
              <p className="font-semibold">{stats?.messages_failed ?? stats?.failed ?? 0}</p>
            </div>
          </div>
        </section>
      )}

      <div className="mb-4 flex gap-2 border-b border-surface-border">
        {(
          [
            ["overview", "Overview"],
            ["messages", "Messages"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={`border-b-2 px-3 py-2 text-sm font-medium ${
              tab === key
                ? "border-sky-600 text-sky-700"
                : "border-transparent text-ink-muted hover:text-ink"
            }`}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "overview" ? (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ["Eligible", stats?.eligible ?? campaign.stats?.eligible ?? 0],
              ["Total snapshotted", stats?.total ?? campaign.stats?.total ?? 0],
              [
                "Excluded / invalid",
                (stats?.excluded ?? 0) + (stats?.invalid ?? 0),
              ],
              ["Suppressed", stats?.suppressed ?? 0],
            ].map(([label, value]) => (
              <div key={String(label)} className="card p-4">
                <p className="text-xs uppercase tracking-wide text-ink-subtle">{label}</p>
                <p className="mt-1 text-2xl font-semibold text-ink">{value}</p>
              </div>
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <section className="card space-y-3 p-5">
              <h2 className="text-base font-semibold text-ink">Summary</h2>
              <dl className="space-y-2 text-sm">
                <div>
                  <dt className="text-ink-subtle">Email account</dt>
                  <dd className="font-medium">
                    {campaign.email_account?.email_address ?? "Not selected"}
                  </dd>
                </div>
                <div>
                  <dt className="text-ink-subtle">Contact list</dt>
                  <dd className="font-medium">{campaign.contact_list?.name ?? "Not selected"}</dd>
                </div>
                <div>
                  <dt className="text-ink-subtle">Content</dt>
                  <dd className="font-medium">
                    {campaign.template?.name ||
                      (campaign.has_content_snapshot ? "Snapshotted content" : "Custom / unset")}
                  </dd>
                </div>
                <div>
                  <dt className="text-ink-subtle">Limits</dt>
                  <dd className="font-medium">
                    {campaign.effective_limits
                      ? `${campaign.effective_limits.daily_limit}/day · ${campaign.effective_limits.hourly_limit}/hour · ${campaign.effective_limits.minimum_delay_seconds}–${campaign.effective_limits.maximum_delay_seconds}s`
                      : "—"}
                  </dd>
                </div>
              </dl>
            </section>

            <section className="card space-y-3 p-5">
              <h2 className="text-base font-semibold text-ink">Validation</h2>
              {validationQuery.data ? (
                <>
                  <p className="text-sm">
                    {validationQuery.data.valid ? (
                      <span className="text-emerald-700">Ready checks passed</span>
                    ) : (
                      <span className="text-red-700">Not ready</span>
                    )}{" "}
                    · {validationQuery.data.eligible_recipients} eligible
                  </p>
                  {validationQuery.data.errors.map((e) => (
                    <p key={e} className="text-sm text-red-700">
                      {e}
                    </p>
                  ))}
                </>
              ) : (
                <p className="text-sm text-ink-muted">Loading…</p>
              )}
            </section>

            <section className="card space-y-3 p-5 lg:col-span-2">
              <h2 className="text-base font-semibold text-ink">Preview</h2>
              {previewQuery.data ? (
                <>
                  <p className="text-sm text-ink-muted">
                    {previewQuery.data.first_name} &lt;{previewQuery.data.email}&gt;
                  </p>
                  <p className="text-sm font-medium">{previewQuery.data.rendered_subject}</p>
                  <div
                    className="prose prose-sm max-w-none rounded-lg border border-surface-border p-4"
                    dangerouslySetInnerHTML={{ __html: previewQuery.data.rendered_html }}
                  />
                </>
              ) : (
                <p className="text-sm text-ink-muted">Preview unavailable.</p>
              )}
            </section>
          </div>
        </>
      ) : null}

      {tab === "messages" ? (
        <section className="card overflow-hidden">
          <div className="flex flex-wrap items-center gap-2 border-b border-surface-border p-4">
            {MESSAGE_FILTERS.map((f) => (
              <button
                key={f || "all"}
                type="button"
                className={`rounded-md px-2 py-1 text-xs font-medium ${
                  messageStatus === f ? "bg-sky-100 text-sky-800" : "text-ink-muted hover:bg-surface-muted"
                }`}
                onClick={() => {
                  setMessageStatus(f);
                  setMessagePage(1);
                }}
              >
                {f ? f.charAt(0).toUpperCase() + f.slice(1) : "All"}
              </button>
            ))}
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-surface-muted text-left text-xs uppercase text-ink-subtle">
                <tr>
                  <th className="px-4 py-3">Recipient</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Attempts</th>
                  <th className="px-4 py-3">Sent at</th>
                  <th className="px-4 py-3">Error</th>
                </tr>
              </thead>
              <tbody>
                {messagesQuery.data?.items.map((m) => (
                  <tr key={m.id} className="border-t border-surface-border">
                    <td className="px-4 py-3">
                      <div className="font-medium">{m.to_name || m.to_email}</div>
                      <div className="text-ink-muted">{m.to_email}</div>
                    </td>
                    <td className="px-4 py-3 capitalize">{m.status}</td>
                    <td className="px-4 py-3">
                      {m.attempt_count}/{m.max_attempts}
                    </td>
                    <td className="px-4 py-3 text-ink-muted">
                      {m.sent_at ? new Date(m.sent_at).toLocaleString() : "—"}
                    </td>
                    <td className="px-4 py-3 text-red-700">
                      {m.error_code || m.error_message
                        ? formatMessageError(m.error_code, m.error_message)
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!messagesQuery.data?.items.length && !messagesQuery.isLoading ? (
            <p className="p-6 text-sm text-ink-muted">No messages yet.</p>
          ) : null}
        </section>
      ) : null}

      <ConfirmDialog
        open={startOpen}
        title="Start campaign?"
        description={[
          `Campaign: ${campaign.name}`,
          `From: ${campaign.email_account?.email_address ?? "—"}`,
          `Recipients: ${validationQuery.data?.eligible_recipients ?? stats?.eligible ?? "—"}`,
          `Daily limit: ${campaign.effective_limits?.daily_limit ?? "—"}`,
          `Hourly limit: ${campaign.effective_limits?.hourly_limit ?? "—"}`,
          `Delay: ${
            campaign.effective_limits
              ? `${campaign.effective_limits.minimum_delay_seconds}–${campaign.effective_limits.maximum_delay_seconds} seconds`
              : "—"
          }`,
          "",
          "Once started, emails will begin sending automatically.",
        ].join("\n")}
        confirmLabel="Start campaign"
        loading={startMutation.isPending}
        onConfirm={() => startMutation.mutate()}
        onCancel={() => setStartOpen(false)}
      />

      <ConfirmDialog
        open={cancelOpen}
        title="Cancel campaign?"
        description={`Cancel “${campaign.name}”? Queued work will stop; sent messages are kept.`}
        confirmLabel="Cancel campaign"
        destructive
        loading={cancelMutation.isPending}
        onCancel={() => setCancelOpen(false)}
        onConfirm={() => cancelMutation.mutate()}
      />
      <ConfirmDialog
        open={deleteOpen}
        title="Delete draft?"
        description={`Delete “${campaign.name}”? This cannot be undone.`}
        confirmLabel="Delete"
        destructive
        loading={deleteMutation.isPending}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => deleteMutation.mutate()}
      />
    </div>
  );
}
