import type { ContactStatus } from "@/types/contacts";
import { cn } from "@/utils/cn";

const styles: Record<ContactStatus, string> = {
  active: "bg-emerald-50 text-emerald-700 ring-emerald-600/15",
  invalid: "bg-amber-50 text-amber-800 ring-amber-600/15",
  unsubscribed: "bg-slate-100 text-slate-700 ring-slate-500/15",
  bounced: "bg-orange-50 text-orange-800 ring-orange-600/15",
  suppressed: "bg-red-50 text-red-700 ring-red-600/15",
};

const labels: Record<ContactStatus, string> = {
  active: "Active",
  invalid: "Invalid",
  unsubscribed: "Unsubscribed",
  bounced: "Bounced",
  suppressed: "Suppressed",
};

export function StatusBadge({ status }: { status: ContactStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        styles[status],
      )}
    >
      {labels[status]}
    </span>
  );
}
