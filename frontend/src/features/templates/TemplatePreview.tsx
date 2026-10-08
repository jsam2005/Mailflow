import type { TemplateRenderResponse } from "@/types/templates";

interface TemplatePreviewProps {
  preview: TemplateRenderResponse | null;
  loading?: boolean;
  label?: string;
}

export function TemplatePreview({
  preview,
  loading,
  label = "Email Preview",
}: TemplatePreviewProps) {
  return (
    <div className="card overflow-hidden">
      <div className="border-b border-surface-border px-4 py-3">
        <h3 className="text-sm font-semibold text-ink">{label}</h3>
        {preview ? (
          <p className="mt-1 text-xs text-ink-subtle">
            Mode: {preview.preview_mode === "sample" ? "Sample Preview" : "Contact"}
          </p>
        ) : null}
      </div>
      <div className="bg-surface-muted p-4">
        {loading ? (
          <div className="h-48 animate-pulse rounded-lg bg-surface" />
        ) : preview ? (
          <div className="mx-auto max-w-[640px] rounded-lg border border-surface-border bg-white shadow-sm">
            <div className="border-b border-surface-border px-5 py-3">
              <p className="text-xs uppercase tracking-wide text-ink-subtle">Subject</p>
              <p className="mt-1 text-sm font-medium text-ink">{preview.rendered_subject}</p>
            </div>
            <div
              className="prose prose-sm max-w-none px-5 py-4 text-ink"
              dangerouslySetInnerHTML={{ __html: preview.rendered_html }}
            />
            <div className="border-t border-surface-border px-5 py-3">
              <p className="text-xs uppercase tracking-wide text-ink-subtle">Plain text</p>
              <pre className="mt-2 whitespace-pre-wrap font-sans text-xs text-ink-muted">
                {preview.rendered_text}
              </pre>
            </div>
          </div>
        ) : (
          <p className="py-10 text-center text-sm text-ink-muted">
            Save or refresh preview to see rendered content.
          </p>
        )}
      </div>
      {preview?.warnings?.length ? (
        <div className="border-t border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">
          {preview.warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </div>
      ) : null}
    </div>
  );
}
