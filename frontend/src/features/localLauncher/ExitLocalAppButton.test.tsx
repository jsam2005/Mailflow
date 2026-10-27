import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { ExitLocalAppButton } from "@/features/localLauncher/ExitLocalAppButton";

describe("ExitLocalAppButton", () => {
  const original = { ...import.meta.env };

  beforeEach(() => {
    vi.stubGlobal("confirm", vi.fn(() => false));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    // Restore env keys used by the helper.
    // @ts-expect-error vitest mutable env
    import.meta.env.VITE_LOCAL_LAUNCHER_URL = original.VITE_LOCAL_LAUNCHER_URL;
    // @ts-expect-error vitest mutable env
    import.meta.env.VITE_LOCAL_LAUNCHER_TOKEN = original.VITE_LOCAL_LAUNCHER_TOKEN;
  });

  it("is hidden when launcher env is absent (hosted / normal dev)", () => {
    // @ts-expect-error vitest mutable env
    import.meta.env.VITE_LOCAL_LAUNCHER_URL = "";
    // @ts-expect-error vitest mutable env
    import.meta.env.VITE_LOCAL_LAUNCHER_TOKEN = "";
    const { container } = render(<ExitLocalAppButton />);
    expect(container).toBeEmptyDOMElement();
  });

  it("is hidden for non-loopback launcher URLs", () => {
    // @ts-expect-error vitest mutable env
    import.meta.env.VITE_LOCAL_LAUNCHER_URL = "https://example.com";
    // @ts-expect-error vitest mutable env
    import.meta.env.VITE_LOCAL_LAUNCHER_TOKEN = "secret";
    const { container } = render(<ExitLocalAppButton />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders in local launcher mode", () => {
    // @ts-expect-error vitest mutable env
    import.meta.env.VITE_LOCAL_LAUNCHER_URL = "http://127.0.0.1:8765";
    // @ts-expect-error vitest mutable env
    import.meta.env.VITE_LOCAL_LAUNCHER_TOKEN = "secret";
    render(<ExitLocalAppButton />);
    expect(screen.getByRole("button", { name: /Exit local app/i })).toBeInTheDocument();
  });
});
