import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchContacts } from "@/api/contacts";
import { templateAssetContentUrl, uploadTemplateAsset } from "@/api/templateAssets";
import {
  createTemplate,
  fetchTemplate,
  renderTemplatePreview,
  updateTemplate,
} from "@/api/templates";
import { PageHeader } from "@/components/PageHeader";
import { useToast } from "@/components/Toast";
import { RichTextEditor } from "@/features/templates/RichTextEditor";
import { TemplatePreview } from "@/features/templates/TemplatePreview";
import { useDebounce } from "@/hooks/useDebounce";
import type { TemplateRenderResponse } from "@/types/templates";
import { getErrorMessage } from "@/utils/errors";

export function TemplateEditorPage() {
  const { id } = useParams();
  const isNew = !id || id === "new";
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [subject, setSubject] = useState("Quick idea for {{company|your business}}");
  const [html, setHtml] = useState(
    "<p>Hi {{first_name|there}},</p><p>I came across {{company|your business}} and wanted to reach out.</p><p>Would you be open to a short conversation?</p><p>Regards,<br/>Selva</p>",
  );
  const [plainText, setPlainText] = useState("");
  const [plainCustomized, setPlainCustomized] = useState(false);
  const [tab, setTab] = useState<"rich" | "plain">("rich");
  const [contactSearch, setContactSearch] = useState("");
  const debouncedContactSearch = useDebounce(contactSearch, 300);
  const [contactId, setContactId] = useState<string>("");
  const [preview, setPreview] = useState<TemplateRenderResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const showPreviewInitially = searchParams.get("preview") === "1";

  const existingQuery = useQuery({
    queryKey: ["template", id],
    queryFn: () => fetchTemplate(id!),
    enabled: !isNew && Boolean(id),
  });

  useEffect(() => {
    if (!existingQuery.data) return;
    const template = existingQuery.data;
    setName(template.name);
    setDescription(template.description || "");
    setSubject(template.subject);
    setHtml(template.html_content);
    setPlainText(template.plain_text_content || "");
    setPlainCustomized(template.plain_text_customized);
  }, [existingQuery.data]);

  const contactsQuery = useQuery({
    queryKey: ["contacts", "preview-select", debouncedContactSearch],
    queryFn: () =>
      fetchContacts({
        page: 1,
        page_size: 10,
        search: debouncedContactSearch,
        status: "",
        company: "",
        contact_list_id: "",
        sort_by: "created_at",
        sort_order: "desc",
      }),
  });

  const previewMutation = useMutation({
    mutationFn: () =>
      renderTemplatePreview({
        subject,
        html_content: html,
        plain_text_content: plainCustomized ? plainText : null,
        contact_id: contactId || null,
        sample_data: contactId
          ? null
          : {
              first_name: "Arun",
              last_name: "Kumar",
              company: "Example Business",
              email: "arun@example.com",
              phone: "9876543210",
              website: "https://example.com",
              metadata: { city: "Chennai" },
            },
      }),
    onSuccess: (data) => {
      setPreview(data);
      setError(null);
    },
    onError: (err) => setError(getErrorMessage(err, "Preview failed")),
  });

  useEffect(() => {
    if (showPreviewInitially || (!isNew && existingQuery.isSuccess)) {
      previewMutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existingQuery.isSuccess, showPreviewInitially]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        name,
        description: description || null,
        subject,
        html_content: html,
        plain_text_content: plainCustomized ? plainText : null,
        plain_text_customized: plainCustomized,
      };
      if (isNew) {
        return createTemplate(payload);
      }
      return updateTemplate(id!, payload);
    },
    onSuccess: async (saved) => {
      pushToast("Template saved.");
      await queryClient.invalidateQueries({ queryKey: ["templates"] });
      await queryClient.invalidateQueries({ queryKey: ["template", saved.id] });
      if (isNew) {
        navigate(`/templates/${saved.id}/edit`, { replace: true });
      }
      previewMutation.mutate();
    },
    onError: (err) => setError(getErrorMessage(err, "Save failed")),
  });

  const uploadImage = async () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/jpeg,image/png,image/webp,image/gif";
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      try {
        const asset = await uploadTemplateAsset(file, isNew ? null : id);
        const src = templateAssetContentUrl(asset.id);
        const img = `<img src="${src}" data-mailflow-asset-id="${asset.id}" alt="" width="${asset.width || ""}" />`;
        setHtml((prev) => `${prev}${img}`);
        pushToast("Image uploaded");
      } catch (err) {
        setError(getErrorMessage(err, "Image upload failed"));
      }
    };
    input.click();
  };

  const contactOptions = contactsQuery.data?.items ?? [];
  const selectedLabel = useMemo(() => {
    const found = contactOptions.find((c) => c.id === contactId);
    if (!found) return "";
    return `${[found.first_name, found.last_name].filter(Boolean).join(" ") || "—"} <${found.email}>`;
  }, [contactOptions, contactId]);

  if (!isNew && existingQuery.isLoading) {
    return <p className="text-sm text-ink-muted">Loading template…</p>;
  }

  return (
    <div>
      <PageHeader
        title={isNew ? "New Template" : "Edit Template"}
        description="Build personalized HTML email content with a plain-text fallback."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link to="/templates" className="btn-secondary">
              Cancel
            </Link>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => previewMutation.mutate()}
              disabled={previewMutation.isPending}
            >
              {previewMutation.isPending ? "Rendering…" : "Refresh Preview"}
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending || !name.trim() || !subject.trim() || !html.trim()}
            >
              {saveMutation.isPending ? "Saving…" : "Save Template"}
            </button>
          </div>
        }
      />

      {error ? (
        <div role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
          <div className="card space-y-4 p-5">
            <div>
              <label className="mb-1.5 block text-sm font-medium">Template name</label>
              <input
                className="input"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Local Business Outreach"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium">Description</label>
              <input
                className="input"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium">Subject</label>
              <input
                className="input"
                value={subject}
                onChange={(event) => setSubject(event.target.value)}
              />
              <p className="mt-1 text-xs text-ink-subtle">
                Supports variables like {"{{company|your business}}"}
              </p>
            </div>
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              className={tab === "rich" ? "btn-primary px-3 py-2" : "btn-secondary px-3 py-2"}
              onClick={() => setTab("rich")}
            >
              Rich Email
            </button>
            <button
              type="button"
              className={tab === "plain" ? "btn-primary px-3 py-2" : "btn-secondary px-3 py-2"}
              onClick={() => setTab("plain")}
            >
              Plain Text
            </button>
          </div>

          {tab === "rich" ? (
            <RichTextEditor value={html} onChange={setHtml} onUploadImage={uploadImage} />
          ) : (
            <div className="card p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <p className="text-sm text-ink-muted">
                  {plainCustomized
                    ? "Custom plain text version"
                    : "Auto-generated from HTML unless customized"}
                </p>
                <button
                  type="button"
                  className="btn-secondary px-3 py-1.5 text-xs"
                  onClick={() => setPlainCustomized(true)}
                >
                  Customize plain text version
                </button>
              </div>
              <textarea
                className="input min-h-[280px] font-mono text-xs"
                value={plainText}
                disabled={!plainCustomized}
                onChange={(event) => {
                  setPlainCustomized(true);
                  setPlainText(event.target.value);
                }}
              />
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="card space-y-3 p-4">
            <h3 className="text-sm font-semibold text-ink">Preview contact</h3>
            <input
              className="input"
              placeholder="Search contacts…"
              value={contactSearch}
              onChange={(event) => setContactSearch(event.target.value)}
            />
            <select
              className="input"
              value={contactId}
              onChange={(event) => setContactId(event.target.value)}
            >
              <option value="">Sample Preview (Arun Kumar)</option>
              {contactOptions.map((contact) => (
                <option key={contact.id} value={contact.id}>
                  {[contact.first_name, contact.last_name].filter(Boolean).join(" ") || "—"} —{" "}
                  {contact.email}
                </option>
              ))}
            </select>
            {selectedLabel ? (
              <p className="text-xs text-ink-subtle">{selectedLabel}</p>
            ) : (
              <p className="text-xs text-ink-subtle">Using sample preview data</p>
            )}
            <button
              type="button"
              className="btn-secondary w-full"
              onClick={() => previewMutation.mutate()}
            >
              Render preview
            </button>
          </div>

          <TemplatePreview preview={preview} loading={previewMutation.isPending} />

          <div className="card p-4 text-xs text-ink-muted">
            <p className="font-medium text-ink">Local image note</p>
            <p className="mt-1">
              Images preview via authenticated local URLs. External recipients cannot load
              localhost images — later sending will use CID inline attachments.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
