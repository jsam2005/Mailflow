import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/Toast";
import { TemplateListPage } from "@/features/templates/TemplateListPage";

vi.mock("@/api/templates", () => ({
  fetchTemplates: vi.fn().mockResolvedValue({
    items: [],
    page: 1,
    page_size: 25,
    total: 0,
    total_pages: 0,
  }),
  deleteTemplate: vi.fn(),
  duplicateTemplate: vi.fn(),
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <ToastProvider>
          <TemplateListPage />
        </ToastProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("TemplateListPage", () => {
  it("renders templates heading and new template CTA", async () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Templates" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /New Template/i })).toHaveAttribute(
      "href",
      "/templates/new",
    );
    await waitFor(() => {
      expect(screen.getByText(/No templates yet/i)).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: /Create your first template/i })).toBeInTheDocument();
  });

  it("renders search input", () => {
    renderPage();
    expect(screen.getByLabelText(/Search templates/i)).toBeInTheDocument();
  });
});
