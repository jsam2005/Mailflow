import type { LucideIcon } from "lucide-react";

import { cn } from "@/utils/cn";

interface StatCardProps {
  label: string;
  value: string;
  hint?: string;
  icon: LucideIcon;
  className?: string;
}

export function StatCard({ label, value, hint, icon: Icon, className }: StatCardProps) {
  return (
    <div className={cn("card p-5", className)}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-ink-muted">{label}</p>
          <p className="mt-2 text-2xl font-semibold tracking-tight text-ink">{value}</p>
          {hint ? <p className="mt-1 text-xs text-ink-subtle">{hint}</p> : null}
        </div>
        <div className="rounded-lg bg-surface-muted p-2.5 text-ink-muted">
          <Icon className="h-5 w-5" aria-hidden />
        </div>
      </div>
    </div>
  );
}
