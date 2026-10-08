import { NavLink } from "react-router-dom";
import { X } from "lucide-react";

import { mainNav } from "@/layouts/nav";
import { cn } from "@/utils/cn";

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ open, onClose }: SidebarProps) {
  return (
    <>
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/30 transition-opacity lg:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={onClose}
        aria-hidden={!open}
      />

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-surface-border bg-surface transition-transform lg:static lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 items-center justify-between border-b border-surface-border px-5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand text-sm font-semibold text-white">
              M
            </div>
            <div>
              <p className="text-sm font-semibold text-ink">MailFlow</p>
              <p className="text-xs text-ink-subtle">Campaign dashboard</p>
            </div>
          </div>
          <button
            type="button"
            className="rounded-md p-1.5 text-ink-muted hover:bg-surface-muted lg:hidden"
            onClick={onClose}
            aria-label="Close menu"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {mainNav.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                onClick={onClose}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition",
                    isActive
                      ? "bg-surface-muted text-ink"
                      : "text-ink-muted hover:bg-surface-muted/70 hover:text-ink",
                  )
                }
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden />
                {item.label}
              </NavLink>
            );
          })}
        </nav>

        <div className="border-t border-surface-border p-4 text-xs text-ink-subtle">
          Phase 1 scaffold
        </div>
      </aside>
    </>
  );
}
