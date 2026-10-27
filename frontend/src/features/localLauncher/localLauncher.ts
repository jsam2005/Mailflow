/** Local launcher mode is injected only when Vite is started by the launcher. */

export function getLocalLauncherConfig(): {
  url: string;
  token: string;
} | null {
  // Hosted / production bundles never enable local exit controls.
  if (!import.meta.env.DEV) {
    return null;
  }
  const url = import.meta.env.VITE_LOCAL_LAUNCHER_URL?.trim();
  const token = import.meta.env.VITE_LOCAL_LAUNCHER_TOKEN?.trim();
  if (!url || !token) {
    return null;
  }
  // Never treat non-loopback URLs as the supported local launcher.
  try {
    const parsed = new URL(url);
    if (!["127.0.0.1", "localhost"].includes(parsed.hostname)) {
      return null;
    }
  } catch {
    return null;
  }
  return { url: url.replace(/\/$/, ""), token };
}

export function isLocalLauncherMode(): boolean {
  return getLocalLauncherConfig() !== null;
}

export async function requestLocalLauncherStop(): Promise<void> {
  const config = getLocalLauncherConfig();
  if (!config) {
    throw new Error("Local launcher mode is not active.");
  }
  const response = await fetch(`${config.url}/api/stop`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${config.token}`,
      "Content-Type": "application/json",
    },
    body: "{}",
  });
  const data = (await response.json().catch(() => ({}))) as {
    ok?: boolean;
    error?: string;
    status?: string;
  };
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || `Stop failed (${response.status})`);
  }
}

export function localLauncherStoppedUrl(): string | null {
  return getLocalLauncherConfig()?.url
    ? `${getLocalLauncherConfig()!.url}/stopped`
    : null;
}
