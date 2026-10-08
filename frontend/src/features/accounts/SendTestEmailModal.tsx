import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchContacts } from "@/api/contacts";
import { fetchTemplates, renderTemplate } from "@/api/templates";
import { Modal } from "@/components/Modal";
import type { EmailAccount, SendTestEmailPayload } from "@/types/emailAccounts";

interface SendTestEmailModalProps {
  open: boolean;
  account: EmailAccount | null;
  submitting?: boolean;
  serverError?: string | null;
  onClose: () => void;
  onSubmit: (payload: SendTestEmailPayload) => Promise<void> | void;
}

export function SendTestEmailModal({
  open,
  account,
  submitting,
  serverError,
  onClose,
  onSubmit,
}: SendTestEmailModalProps) {
  const [mode, setMode] = useState<"simple" | "template">("simple");
  const [toEmail, setToEmail] = useState("");
  const [subject, setSubject] = useState("MailFlow test email");
  const [message, setMessage] = useState("This is a test email sent from MailFlow.");
  const [templateId, setTemplateId] = useState("");
  const [contactId, setContactId] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const templatesQuery = useQuery({
    queryKey: ["templates", "send-test"],
    queryFn: () =>
      fetchTemplates({
        page: 1,
        page_size: 100,
        search: "",
        sort_by: "updated_at",
        sort_order: "desc",
      }),
    enabled: open && mode === "template",
  });

  const contactsQuery = useQuery({
    queryKey: ["contacts", "send-test"],
    queryFn: () =>
      fetchContacts({
        page: 1,
        page_size: 100,
        search: "",
        status: "",
        company: "",
        contact_list_id: "",
        sort_by: "created_at",
        sort_order: "desc",
      }),
    enabled: open && mode === "template",
  });

  const previewQuery = useQuery({
    queryKey: ["template-render", templateId, contactId],
    queryFn: () =>
      renderTemplate(templateId, {
        contact_id: contactId || null,
      }),
    enabled: open && mode === "template" && Boolean(templateId),
  });

  useEffect(() => {
    if (!open) return;
    setMode("simple");
    setToEmail("");
    setSubject("MailFlow test email");
    setMessage("This is a test email sent from MailFlow.");
    setTemplateId("");
    setContactId("");
    setLocalError(null);
  }, [open, account?.id]);

  const handleSend = () => {
    setLocalError(null);
    if (!toEmail.trim()) {
      setLocalError("Recipient email is required.");
      return;
    }
    if (mode === "template" && !templateId) {
      setLocalError("Select a template.");
      return;
    }
    const payload: SendTestEmailPayload =
      mode === "simple"
        ? {
            to_email: toEmail.trim(),
            mode: "simple",
            subject: subject.trim() || "MailFlow test email",
            message: message.trim() || "This is a test email sent from MailFlow.",
          }
        : {
            to_email: toEmail.trim(),
            mode: "template",
            template_id: templateId,
            contact_id: contactId || undefined,
          };
    void onSubmit(payload);
  };

  return (
    <Modal
      open={open}
      title="Send test email"
      size="lg"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </button>
          <button type="button" className="btn-primary" onClick={handleSend} disabled={submitting}>
            {submitting ? "Sending…" : "Send Test Email"}
          </button>
        </>
      }
    >
      {account ? (
        <p className="mb-4 text-sm text-ink-muted">
          Sending from <span className="font-medium text-ink">{account.email_address}</span>
        </p>
      ) : null}

      <div className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-ink" htmlFor="test-to-email">
            Recipient email
          </label>
          <input
            id="test-to-email"
            type="email"
            className="input"
            value={toEmail}
            onChange={(e) => setToEmail(e.target.value)}
          />
        </div>

        <fieldset>
          <legend className="mb-2 text-sm font-medium text-ink">Mode</legend>
          <div className="flex gap-4">
            <label className="inline-flex items-center gap-2 text-sm text-ink">
              <input
                type="radio"
                name="test-mode"
                checked={mode === "simple"}
                onChange={() => setMode("simple")}
              />
              Simple message
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-ink">
              <input
                type="radio"
                name="test-mode"
                checked={mode === "template"}
                onChange={() => setMode("template")}
              />
              Existing template
            </label>
          </div>
        </fieldset>

        {mode === "simple" ? (
          <>
            <div>
              <label className="mb-1 block text-sm font-medium text-ink" htmlFor="test-subject">
                Subject
              </label>
              <input
                id="test-subject"
                className="input"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-ink" htmlFor="test-message">
                Message
              </label>
              <textarea
                id="test-message"
                className="input min-h-[120px]"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
              />
            </div>
          </>
        ) : (
          <>
            <div>
              <label className="mb-1 block text-sm font-medium text-ink" htmlFor="test-template">
                Template
              </label>
              <select
                id="test-template"
                className="input"
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
              >
                <option value="">Select template…</option>
                {(templatesQuery.data?.items ?? []).map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-ink" htmlFor="test-contact">
                Preview contact (optional)
              </label>
              <select
                id="test-contact"
                className="input"
                value={contactId}
                onChange={(e) => setContactId(e.target.value)}
              >
                <option value="">Sample data</option>
                {(contactsQuery.data?.items ?? []).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.email}
                    {c.first_name ? ` (${c.first_name})` : ""}
                  </option>
                ))}
              </select>
            </div>
            {previewQuery.data ? (
              <div className="rounded-lg border border-surface-border bg-surface-muted p-3">
                <p className="text-xs font-medium uppercase tracking-wide text-ink-subtle">
                  Preview
                </p>
                <p className="mt-1 text-sm font-medium text-ink">
                  {previewQuery.data.rendered_subject}
                </p>
                <div
                  className="prose prose-sm mt-2 max-w-none text-ink"
                  dangerouslySetInnerHTML={{ __html: previewQuery.data.rendered_html }}
                />
              </div>
            ) : null}
          </>
        )}

        {localError || serverError ? (
          <p className="text-sm text-red-600">{localError || serverError}</p>
        ) : null}
      </div>
    </Modal>
  );
}
