import { useState } from "react";
import { Power } from "lucide-react";

import {
  isLocalLauncherMode,
  localLauncherStoppedUrl,
  requestLocalLauncherStop,
} from "@/features/localLauncher/localLauncher";

/**
 * Visible only when Vite was started by the local launcher (env injected).
 * Hosted / normal npm run dev builds omit those vars, so this stays hidden.
 */
export function ExitLocalAppButton() {
  const enabled = isLocalLauncherMode();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!enabled) {
    return null;
  }

  async function onExit() {
    const confirmed = window.confirm(
      "Exit the local MailFlow app? This stops launcher-owned services and can interrupt sending or imports in progress.",
    );
    if (!confirmed) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await requestLocalLauncherStop();
      const stopped = localLauncherStoppedUrl();
      if (stopped) {
        window.location.assign(stopped);
        return;
      }
      setError("Stopped, but could not open the launcher stopped screen.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not stop MailFlow.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={onExit}
        disabled={busy}
        className="btn-secondary gap-2 px-3 py-2 text-amber-900"
        title="Stop local MailFlow (launcher mode only)"
      >
        <Power className="h-4 w-4" />
        <span className="hidden sm:inline">{busy ? "Stopping…" : "Exit local app"}</span>
      </button>
      {error ? <p className="max-w-[14rem] text-right text-xs text-red-600">{error}</p> : null}
    </div>
  );
}
