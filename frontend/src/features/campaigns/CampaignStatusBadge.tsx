import type { CampaignStatus } from "@/types/campaigns";
import { cn } from "@/utils/cn";

const styles: Record<string, string> = {
  draft: "bg-slate-100 text-slate-700 ring-slate-500/15",
  ready: "bg-emerald-50 text-emerald-700 ring-emerald-600/15",
  cancelled: "bg-red-50 text-red-700 ring-red-600/15",
  running: "bg-sky-50 text-sky-700 ring-sky-600/15",
  paused: "bg-amber-50 text-amber-800 ring-amber-600/15",
  completed: "bg-indigo-50 text-indigo-700 ring-indigo-600/15",
};

const labels: Record<string, string> = {
  draft: "Draft",
  ready: "Ready",
  cancelled: "Cancelled",
  running: "Running",
  paused: "Paused",
  completed: "Completed",
};

export function CampaignStatusBadge({ status }: { status: CampaignStatus | string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        styles[status] ?? styles.draft,
      )}
    >
      {labels[status] ?? status}
    </span>
  );
}
