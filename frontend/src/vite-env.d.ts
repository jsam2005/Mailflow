/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  /** Injected only when Vite is started by the local launcher (loopback). */
  readonly VITE_LOCAL_LAUNCHER_URL?: string;
  readonly VITE_LOCAL_LAUNCHER_TOKEN?: string;
  /** "1" in the Windows exe build: open without a login screen. */
  readonly VITE_MAILFLOW_DESKTOP?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
