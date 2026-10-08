import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Megaphone, Plus, Search, Trash2 } from "lucide-react";

import {
  cancelCampaign,
  deleteCampaign,
  fetchCampaigns,
} from "@/api/campaigns";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PageHeader } from "@/components/PageHeader";
import { useToast } from "@/components/Toast";
import { CampaignStatusBadge } from "@/features/campaigns/CampaignStatusBadge";
import { useDebounce } from "@/hooks/useDebounce";
import type { Campaign, CampaignFilters } from "@/types/campaigns";
import { getErrorMessage } from "@/utils/errors";

const defaultFilters: CampaignFilters = {
  page: 1,
  page_size: 25,
  search: "",
  status: "",
  sort_by: "updated_at",
  sort_order: "desc",
};

export function CampaignListPage() {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();
  const [filters, setFilters] = useState<CampaignFilters>(defaultFilters);
  const [searchInput, setSearchInput] = useState("");
  const debouncedSearch = useDebounce(searchInput, 400);
  const activeFilters = useMemo(
    () => ({ ...filters, search: debouncedSearch }),
    [filters, debouncedSearch],
  );
  const [deleteTarget, setDeleteTarget] = useState<Campaign | null>(null);
  const [cancelTarget, setCancelTarget] = useState<Campaign | null>(null);

  const campaignsQuery = useQuery({
    queryKey: ["campaigns", activeFilters],
    queryFn: () => fetchCampaigns(activeFilters),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteCampaign(id),
    onSuccess: async () => {
      setDeleteTarget(null);
      pushToast("Draft campaign deleted");
      await queryClient.invalidateQueries({ queryKey: ["campaigns"] });
    },
    onError: (error) => pushToast(getErrorMessage(error), "error"),
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => cancelCampaign(id),
    onSuccess: async () => {
      setCancelTarget(null);
      pushToast("Campaign cancelled");
      await queryClient.invalidateQueries({ queryKey: ["campaigns"] });
    },
    onError: (error) => pushToast(getErrorMessage(error), "error"),
  });

  const items = campaignsQuery.data?.items ?? [];

  return (
    <div>
      <PageHeader
        title="Campaigns"
        description="Create and manage email outreach campaigns."
        actions={
          <Link to="/campaigns/new" className="btn-primary inline-flex items-center">
            <Plus className="mr-2 h-4 w-4" />
            New Campaign
          </Link>
        }
      />

      <div className="card overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-surface-border p-4 sm:flex-row sm:items-center">
          <div className="relative max-w-md flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" />
            <input
              aria-label="Search campaigns"
              className="input pl-9"
              placeholder="Search by name…"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
          </div>
          <select
            aria-label="Filter by status"
            className="input w-full sm:w-40"
            value={filters.status}
            onChange={(e) =>
              setFilters((f) => ({
                ...f,
                status: e.target.value as CampaignFilters["status"],
                page: 1,
              }))
            }
          >
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="ready">Ready</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>

        {campaignsQuery.isLoading ? (
          <p className="p-6 text-sm text-ink-muted">Loading campaigns…</p>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-start gap-4 p-8">
            <div className="rounded-lg bg-surface-muted p-3">
              <Megaphone className="h-6 w-6 text-ink-muted" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-ink">No campaigns yet</h2>
              <p className="mt-1 text-sm text-ink-muted">
                Create a campaign to plan recipients, content, and sending settings.
              </p>
            </div>
            <Link to="/campaigns/new" className="btn-primary">
              Create your first campaign
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-surface-border bg-surface-muted/50 text-xs uppercase tracking-wide text-ink-subtle">
                <tr>
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Recipients</th>
                  <th className="px-4 py-3 font-medium">Email account</th>
                  <th className="px-4 py-3 font-medium">Updated</th>
                  <th className="px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((campaign) => (
                  <tr key={campaign.id} className="border-b border-surface-border last:border-0">
                    <td className="px-4 py-3">
                      <Link
                        to={`/campaigns/${campaign.id}`}
                        className="font-medium text-ink hover:text-brand"
                      >
                        {campaign.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <CampaignStatusBadge status={campaign.status} />
                    </td>
                    <td className="px-4 py-3 text-ink-muted">
                      {campaign.stats
                        ? `${campaign.stats.eligible} eligible / ${campaign.stats.total}`
                        : "—"}
                    </td>
                    <td className="px-4 py-3 text-ink-muted">
                      {campaign.email_account?.email_address ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-ink-muted">
                      {new Date(campaign.updated_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-2">
                        <Link to={`/campaigns/${campaign.id}`} className="btn-secondary text-xs">
                          View
                        </Link>
                        {campaign.status === "draft" ? (
                          <>
                            <Link
                              to={`/campaigns/${campaign.id}/edit`}
                              className="btn-secondary text-xs"
                            >
                              Edit
                            </Link>
                            <button
                              type="button"
                              className="btn-secondary inline-flex items-center text-xs text-red-700"
                              onClick={() => setDeleteTarget(campaign)}
                            >
                              <Trash2 className="mr-1 h-3 w-3" />
                              Delete
                            </button>
                          </>
                        ) : null}
                        {campaign.status === "ready" ? (
                          <button
                            type="button"
                            className="btn-secondary text-xs text-red-700"
                            onClick={() => setCancelTarget(campaign)}
                          >
                            Cancel
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete draft campaign?"
        description={
          deleteTarget
            ? `Delete “${deleteTarget.name}”? This cannot be undone.`
            : ""
        }
        confirmLabel="Delete"
        destructive
        loading={deleteMutation.isPending}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
      />

      <ConfirmDialog
        open={Boolean(cancelTarget)}
        title="Cancel ready campaign?"
        description={
          cancelTarget
            ? `Cancel “${cancelTarget.name}”? Recipient history will remain.`
            : ""
        }
        confirmLabel="Cancel campaign"
        destructive
        loading={cancelMutation.isPending}
        onCancel={() => setCancelTarget(null)}
        onConfirm={() => cancelTarget && cancelMutation.mutate(cancelTarget.id)}
      />
    </div>
  );
}
