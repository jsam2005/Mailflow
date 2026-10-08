import { useState } from "react";
import { Outlet } from "react-router-dom";
import { LogOut, Menu } from "lucide-react";

import { useAuth } from "@/features/auth/AuthContext";
import { Sidebar } from "@/layouts/Sidebar";

export function AppLayout() {
  const { user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-surface-muted">
      <Sidebar open={mobileOpen} onClose={() => setMobileOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-surface-border bg-surface/95 px-4 backdrop-blur sm:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="rounded-md p-2 text-ink-muted hover:bg-surface-muted lg:hidden"
              onClick={() => setMobileOpen(true)}
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5" />
            </button>
            <p className="text-sm text-ink-muted lg:hidden">MailFlow</p>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <p className="text-sm font-medium text-ink">{user?.name}</p>
              <p className="text-xs text-ink-subtle">{user?.email}</p>
            </div>
            <button
              type="button"
              onClick={logout}
              className="btn-secondary gap-2 px-3 py-2"
              title="Sign out"
            >
              <LogOut className="h-4 w-4" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-8">
          <div className="mx-auto max-w-7xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
