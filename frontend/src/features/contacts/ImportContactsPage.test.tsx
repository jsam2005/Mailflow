import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/Toast";
import { ImportContactsPage } from "@/features/contacts/ImportContactsPage";

vi.mock("@/api/contactLists", () => ({
  fetchContactLists: vi.fn().mockResolvedValue([]),
}));

vi.mock("@/api/imports", () => ({
  uploadImportFile: vi.fn(),
  validateImport: vi.fn(),
  executeImport: vi.fn(),
  cancelImport: vi.fn(),
  fetchImportHistory: vi.fn(),
}));

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <ToastProvider>
          <ImportContactsPage />
        </ToastProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("ImportContactsPage", () => {
  it("renders upload step", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Import Contacts" })).toBeInTheDocument();
    expect(screen.getByText(/Upload your contact dataset/i)).toBeInTheDocument();
    expect(screen.getByText(/CSV or XLSX up to 10 MB/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Continue/i })).toBeDisabled();
  });

  it("rejects unsupported file extensions client-side", () => {
    renderPage();

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["hello"], "notes.txt", { type: "text/plain" });
    fireEvent.change(input, { target: { files: [file] } });

    expect(screen.getByText(/must be CSV or XLSX/i)).toBeInTheDocument();
  });
});
