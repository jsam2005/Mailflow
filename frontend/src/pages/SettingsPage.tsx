import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { useAuth } from "@/features/auth/AuthContext";

interface HealthPayload {
  status: string;
  database?: string | null;
  version?: string | null;
  environment?: string | null;
  storage_provider?: string | null;
  scheduler_mode?: string | null;
}

export function SettingsPage() {
  const { user } = useAuth();
  const healthQuery = useQuery({
    queryKey: ["system-health"],
    queryFn: async () => {
      const { data } = await apiClient.get<HealthPayload>("/api/v1/health");
      return data;
    },
  });

  const health = healthQuery.data;

  return (
    <div>
      <PageHeader
        title="Settings"
        description="Account preferences and production system status."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card max-w-xl p-6">
          <h2 className="text-sm font-semibold text-ink">Admin account</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between gap-4 border-b border-surface-border pb-3">
              <dt className="text-ink-muted">Name</dt>
              <dd className="font-medium text-ink">{user?.name}</dd>
            </div>
            <div className="flex justify-between gap-4 border-b border-surface-border pb-3">
              <dt className="text-ink-muted">Email</dt>
              <dd className="font-medium text-ink">{user?.email}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-muted">Access</dt>
              <dd className="font-medium text-ink">Private admin (no public signup)</dd>
            </div>
          </dl>
        </div>

        <div className="card max-w-xl p-6">
          <h2 className="text-sm font-semibold text-ink">System status</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between gap-4 border-b border-surface-border pb-3">
              <dt className="text-ink-muted">Database</dt>
              <dd className="font-medium text-ink">
                {health?.database === "ok" ? "Connected" : healthQuery.isLoading ? "…" : "Unavailable"}
              </dd>
            </div>
            <div className="flex justify-between gap-4 border-b border-surface-border pb-3">
              <dt className="text-ink-muted">Environment</dt>
              <dd className="font-medium text-ink capitalize">{health?.environment ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-4 border-b border-surface-border pb-3">
              <dt className="text-ink-muted">Storage</dt>
              <dd className="font-medium text-ink">{health?.storage_provider ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-4 border-b border-surface-border pb-3">
              <dt className="text-ink-muted">Worker mode</dt>
              <dd className="font-medium text-ink">{health?.scheduler_mode ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-muted">Version</dt>
              <dd className="font-medium text-ink">{health?.version ?? "—"}</dd>
            </div>
          </dl>
          <p className="mt-4 text-xs text-ink-subtle">Secrets are never displayed here.</p>
        </div>
      </div>
    </div>
  );
}
