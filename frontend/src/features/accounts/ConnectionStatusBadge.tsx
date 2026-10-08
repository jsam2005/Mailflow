import type { ConnectionStatus } from "@/types/emailAccounts";
import { cn } from "@/utils/cn";

const styles: Record<ConnectionStatus, string> = {
  connected: "bg-emerald-50 text-emerald-700 ring-emerald-600/15",
  expired: "bg-amber-50 text-amber-800 ring-amber-600/15",
  error: "bg-red-50 text-red-700 ring-red-600/15",
  disconnected: "bg-slate-100 text-slate-700 ring-slate-500/15",
};

const labels: Record<ConnectionStatus, string> = {
  connected: "Connected",
  expired: "Expired",
  error: "Error",
  disconnected: "Disconnected",
};

export function ConnectionStatusBadge({ status }: { status: ConnectionStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        styles[status] ?? styles.disconnected,
      )}
    >
      {labels[status] ?? status}
    </span>
  );
}
