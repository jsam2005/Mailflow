import { useState } from "react";

import { Modal } from "@/components/Modal";

const BUILTINS: { key: string; label: string }[] = [
  { key: "first_name", label: "First Name" },
  { key: "last_name", label: "Last Name" },
  { key: "full_name", label: "Full Name" },
  { key: "company", label: "Company" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Phone" },
  { key: "website", label: "Website" },
];

interface PersonalizationMenuProps {
  onInsert: (token: string) => void;
}

export function PersonalizationMenu({ onInsert }: PersonalizationMenuProps) {
  const [open, setOpen] = useState(false);
  const [fallbackOpen, setFallbackOpen] = useState(false);
  const [selectedKey, setSelectedKey] = useState("first_name");
  const [fallback, setFallback] = useState("");
  const [customKey, setCustomKey] = useState("");
  const [customMode, setCustomMode] = useState(false);

  const insertWithFallback = () => {
    const key = customMode ? `meta.${customKey.trim()}` : selectedKey;
    if (!key || key === "meta.") return;
    const token = fallback.trim() ? `{{${key}|${fallback.trim()}}}` : `{{${key}}}`;
    onInsert(token);
    setFallbackOpen(false);
    setOpen(false);
    setFallback("");
    setCustomKey("");
    setCustomMode(false);
  };

  return (
    <div className="relative">
      <button type="button" className="btn-secondary px-3 py-1.5 text-xs" onClick={() => setOpen((v) => !v)}>
        Personalize
      </button>
      {open ? (
        <div className="absolute left-0 z-20 mt-1 w-52 rounded-lg border border-surface-border bg-surface py-1 shadow-card">
          {BUILTINS.map((item) => (
            <button
              key={item.key}
              type="button"
              className="block w-full px-3 py-2 text-left text-sm hover:bg-surface-muted"
              onClick={() => {
                setSelectedKey(item.key);
                setCustomMode(false);
                setFallbackOpen(true);
              }}
            >
              {item.label}
            </button>
          ))}
          <button
            type="button"
            className="block w-full border-t border-surface-border px-3 py-2 text-left text-sm hover:bg-surface-muted"
            onClick={() => {
              setCustomMode(true);
              setFallbackOpen(true);
            }}
          >
            Custom Field…
          </button>
        </div>
      ) : null}

      <Modal
        open={fallbackOpen}
        title="Insert variable"
        onClose={() => setFallbackOpen(false)}
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setFallbackOpen(false)}>
              Cancel
            </button>
            <button type="button" className="btn-primary" onClick={insertWithFallback}>
              Insert
            </button>
          </>
        }
      >
        <div className="space-y-3">
          {customMode ? (
            <div>
              <label className="mb-1.5 block text-sm font-medium">Metadata key</label>
              <input
                className="input"
                placeholder="city"
                value={customKey}
                onChange={(event) => setCustomKey(event.target.value)}
              />
              <p className="mt-1 text-xs text-ink-subtle">Inserts {"{{meta.key}}"}</p>
            </div>
          ) : (
            <p className="text-sm text-ink-muted">
              Variable: <span className="font-medium text-ink">{selectedKey}</span>
            </p>
          )}
          <div>
            <label className="mb-1.5 block text-sm font-medium">Fallback (optional)</label>
            <input
              className="input"
              placeholder="there"
              value={fallback}
              onChange={(event) => setFallback(event.target.value)}
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}
