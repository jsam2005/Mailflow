import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, FileText, MoreHorizontal, Pencil, Plus, Search, Trash2 } from "lucide-react";

import { deleteTemplate, duplicateTemplate, fetchTemplates } from "@/api/templates";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PageHeader } from "@/components/PageHeader";
import { useToast } from "@/components/Toast";
import { useDebounce } from "@/hooks/useDebounce";
import type { EmailTemplate, TemplateFilters } from "@/types/templates";
import { getErrorMessage } from "@/utils/errors";

const defaultFilters: TemplateFilters = {
  page: 1,
  page_size: 25,
  search: "",
  sort_by: "updated_at",
  sort_order: "desc",
};

export function TemplateListPage() {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();
  const [filters, setFilters] = useState<TemplateFilters>(defaultFilters);
  const [searchInput, setSearchInput] = useState("");
  const debouncedSearch = useDebounce(searchInput, 400);
  const activeFilters = useMemo(
    () => ({ ...filters, search: debouncedSearch }),
    [filters, debouncedSearch],
  );
  const [menuId, setMenuId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<EmailTemplate | null>(null);

  const templatesQuery = useQuery({
    queryKey: ["templates", activeFilters],
    queryFn: () => fetchTemplates(activeFilters),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteTemplate(id),
    onSuccess: async () => {
      setDeleteTarget(null);
      pushToast("Template deleted");
      await queryClient.invalidateQueries({ queryKey: ["templates"] });
    },
    onError: (error) => pushToast(getErrorMessage(error), "error"),
  });

  const duplicateMutation = useMutation({
    mutationFn: (id: string) => duplicateTemplate(id),
    onSuccess: async () => {
      pushToast("Template duplicated");
      setMenuId(null);
      await queryClient.invalidateQueries({ queryKey: ["templates"] });
    },
    onError: (error) => pushToast(getErrorMessage(error), "error"),
  });

  const items = templatesQuery.data?.items ?? [];

  return (
    <div>
      <PageHeader
        title="Templates"
        description="Create reusable personalized email content."
        actions={
          <Link to="/templates/new" className="btn-primary inline-flex items-center">
            <Plus className="mr-2 h-4 w-4" />
            New Template
          </Link>
        }
      />

      <div className="card overflow-hidden">
        <div className="border-b border-surface-border p-4">
          <div className="relative max-w-md">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" />
            <input
              aria-label="Search templates"
              className="input pl-9"
              placeholder="Search name or subject…"
              value={searchInput}
              onChange={(event) => {
                setSearchInput(event.target.value);
                setFilters((prev) => ({ ...prev, page: 1 }));
              }}
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-surface-muted/50 text-xs uppercase tracking-wide text-ink-subtle">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Subject</th>
                <th className="px-4 py-3 font-medium">Updated</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {templatesQuery.isLoading ? (
                Array.from({ length: 4 }).map((_, index) => (
                  <tr key={index}>
                    <td colSpan={5} className="px-4 py-3">
                      <div className="h-8 animate-pulse rounded bg-surface-muted" />
                    </td>
                  </tr>
                ))
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center">
                    <FileText className="mx-auto mb-3 h-8 w-8 text-ink-subtle" />
                    <p className="text-sm font-medium text-ink">No templates yet.</p>
                    <Link to="/templates/new" className="btn-primary mt-4 inline-flex">
                      Create your first template
                    </Link>
                  </td>
                </tr>
              ) : (
                items.map((template) => (
                  <tr key={template.id} className="hover:bg-surface-muted/40">
                    <td className="px-4 py-3 font-medium text-ink">{template.name}</td>
                    <td className="max-w-xs truncate px-4 py-3 text-ink-muted">
                      {template.subject}
                    </td>
                    <td className="px-4 py-3 text-ink-muted">
                      {new Date(template.updated_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded-md bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-600/15">
                        {template.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="relative px-4 py-3">
                      <button
                        type="button"
                        className="rounded-md p-1.5 text-ink-muted hover:bg-surface-muted"
                        aria-label={`Actions for ${template.name}`}
                        onClick={() =>
                          setMenuId((prev) => (prev === template.id ? null : template.id))
                        }
                      >
                        <MoreHorizontal className="h-4 w-4" />
                      </button>
                      {menuId === template.id ? (
                        <div className="absolute right-4 z-10 mt-1 w-40 rounded-lg border border-surface-border bg-surface py-1 shadow-card">
                          <Link
                            to={`/templates/${template.id}/edit`}
                            className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-surface-muted"
                          >
                            <Pencil className="h-3.5 w-3.5" /> Edit
                          </Link>
                          <Link
                            to={`/templates/${template.id}/edit?preview=1`}
                            className="block px-3 py-2 text-sm hover:bg-surface-muted"
                          >
                            Preview
                          </Link>
                          <button
                            type="button"
                            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-surface-muted"
                            onClick={() => duplicateMutation.mutate(template.id)}
                          >
                            <Copy className="h-3.5 w-3.5" /> Duplicate
                          </button>
                          <button
                            type="button"
                            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-red-700 hover:bg-surface-muted"
                            onClick={() => {
                              setDeleteTarget(template);
                              setMenuId(null);
                            }}
                          >
                            <Trash2 className="h-3.5 w-3.5" /> Delete
                          </button>
                        </div>
                      ) : null}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between border-t border-surface-border px-4 py-3">
          <p className="text-sm text-ink-muted">
            {templatesQuery.data
              ? `${templatesQuery.data.total} template${templatesQuery.data.total === 1 ? "" : "s"}`
              : "—"}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              className="btn-secondary px-3 py-2"
              disabled={filters.page <= 1}
              onClick={() => setFilters((prev) => ({ ...prev, page: prev.page - 1 }))}
            >
              Previous
            </button>
            <button
              type="button"
              className="btn-secondary px-3 py-2"
              disabled={
                !templatesQuery.data ||
                filters.page >= (templatesQuery.data.total_pages || 1)
              }
              onClick={() => setFilters((prev) => ({ ...prev, page: prev.page + 1 }))}
            >
              Next
            </button>
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete template?"
        description={
          deleteTarget
            ? `This will permanently delete “${deleteTarget.name}”.`
            : ""
        }
        confirmLabel="Delete"
        destructive
        loading={deleteMutation.isPending}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
        }}
      />
    </div>
  );
}
