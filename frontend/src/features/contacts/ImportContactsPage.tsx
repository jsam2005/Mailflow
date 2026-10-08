import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileSpreadsheet, Upload, X } from "lucide-react";

import { fetchContactLists } from "@/api/contactLists";
import {
  cancelImport,
  executeImport,
  uploadImportFile,
  validateImport,
} from "@/api/imports";
import { PageHeader } from "@/components/PageHeader";
import { StatCard } from "@/components/StatCard";
import { useToast } from "@/components/Toast";
import type {
  ImportExecuteResponse,
  ImportUploadResponse,
  ImportValidationResponse,
  MappingTarget,
} from "@/types/imports";
import { getErrorMessage } from "@/utils/errors";
import { cn } from "@/utils/cn";

const STEPS = ["Upload", "Map Columns", "Validate", "Review", "Complete"] as const;

const TARGET_OPTIONS: { value: MappingTarget; label: string }[] = [
  { value: "ignore", label: "Ignore" },
  { value: "email", label: "Email" },
  { value: "first_name", label: "First Name" },
  { value: "last_name", label: "Last Name" },
  { value: "full_name", label: "Full Name" },
  { value: "company", label: "Company" },
  { value: "phone", label: "Phone" },
  { value: "website", label: "Website" },
  { value: "custom", label: "Custom Field" },
];

const exclusiveTargets = new Set([
  "email",
  "first_name",
  "last_name",
  "full_name",
  "company",
  "phone",
  "website",
]);

type StepIndex = 0 | 1 | 2 | 3 | 4;

export function ImportContactsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  const [step, setStep] = useState<StepIndex>(0);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [upload, setUpload] = useState<ImportUploadResponse | null>(null);
  const [mapping, setMapping] = useState<Record<string, MappingTarget>>({});
  const [sheet, setSheet] = useState<string>("");
  const [validation, setValidation] = useState<ImportValidationResponse | null>(null);
  const [issueTab, setIssueTab] = useState<
    "invalid" | "missing" | "duplicates" | "existing"
  >("invalid");
  const [listMode, setListMode] = useState<"existing" | "new">("existing");
  const [selectedListId, setSelectedListId] = useState("");
  const [newListName, setNewListName] = useState("");
  const [newListDescription, setNewListDescription] = useState("");
  const [result, setResult] = useState<ImportExecuteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const listsQuery = useQuery({
    queryKey: ["contact-lists"],
    queryFn: fetchContactLists,
  });

  const emailMapped = Object.values(mapping).includes("email");

  const mappingConflict = useMemo(() => {
    const counts = new Map<string, number>();
    for (const target of Object.values(mapping)) {
      if (!exclusiveTargets.has(target)) continue;
      counts.set(target, (counts.get(target) || 0) + 1);
    }
    return [...counts.entries()].some(([, count]) => count > 1);
  }, [mapping]);

  const uploadMutation = useMutation({
    mutationFn: (selected: File) => uploadImportFile(selected),
    onSuccess: (data) => {
      setUpload(data);
      setSheet(data.default_sheet || "");
      const next: Record<string, MappingTarget> = {};
      for (const column of data.columns) {
        next[column] = (data.suggested_mapping[column] as MappingTarget) || "ignore";
      }
      setMapping(next);
      setError(null);
      setStep(1);
      pushToast("File uploaded successfully.");
    },
    onError: (err) => setError(getErrorMessage(err, "Upload failed")),
  });

  const validateMutation = useMutation({
    mutationFn: () => {
      if (!upload) throw new Error("Missing upload");
      return validateImport(upload.import_session_id, {
        column_mapping: mapping,
        sheet: sheet || null,
        contact_list_id:
          listMode === "existing" && selectedListId ? selectedListId : null,
      });
    },
    onSuccess: (data) => {
      setValidation(data);
      setError(null);
      setStep(2);
    },
    onError: (err) => setError(getErrorMessage(err, "Validation failed")),
  });

  const executeMutation = useMutation({
    mutationFn: () => {
      if (!upload) throw new Error("Missing upload");
      return executeImport(upload.import_session_id, {
        contact_list_id: listMode === "existing" ? selectedListId : null,
        new_list_name: listMode === "new" ? newListName : null,
        new_list_description: listMode === "new" ? newListDescription : null,
        column_mapping: mapping,
        sheet: sheet || null,
      });
    },
    onSuccess: async (data) => {
      setResult(data);
      setStep(4);
      await queryClient.invalidateQueries({ queryKey: ["contacts"] });
      await queryClient.invalidateQueries({ queryKey: ["contact-lists"] });
      pushToast(`Imported ${data.imported_rows} contacts`);
    },
    onError: (err) => setError(getErrorMessage(err, "Import failed")),
  });

  const onFileChosen = (selected: File | null) => {
    if (!selected) return;
    const lower = selected.name.toLowerCase();
    if (!lower.endsWith(".csv") && !lower.endsWith(".xlsx")) {
      setError("The selected file must be CSV or XLSX.");
      return;
    }
    if (selected.size > 10 * 1024 * 1024) {
      setError("File exceeds the 10 MB import limit.");
      return;
    }
    setFile(selected);
    setError(null);
  };

  const updateMapping = (column: string, target: MappingTarget) => {
    setMapping((prev) => ({ ...prev, [column]: target }));
  };

  const canContinueReview =
    listMode === "existing" ? Boolean(selectedListId) : newListName.trim().length > 0;

  return (
    <div>
      <PageHeader
        title="Import Contacts"
        description="Upload a CSV or XLSX dataset, map columns, validate, and import."
        actions={
          <Link to="/contacts" className="btn-secondary">
            Back to Contacts
          </Link>
        }
      />

      <ol className="mb-6 flex flex-wrap gap-2">
        {STEPS.map((label, index) => (
          <li
            key={label}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium",
              index === step
                ? "bg-brand text-white"
                : index < step
                  ? "bg-emerald-50 text-emerald-700"
                  : "bg-surface-muted text-ink-subtle",
            )}
          >
            {index + 1}. {label}
          </li>
        ))}
      </ol>

      {error ? (
        <div role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      {step === 0 ? (
        <div className="card p-6">
          <div
            className={cn(
              "flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-16 text-center transition",
              dragOver ? "border-brand bg-surface-muted" : "border-surface-border",
            )}
            onDragOver={(event) => {
              event.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragOver(false);
              onFileChosen(event.dataTransfer.files?.[0] || null);
            }}
          >
            <Upload className="mb-3 h-8 w-8 text-ink-subtle" />
            <p className="text-base font-medium text-ink">Upload your contact dataset</p>
            <p className="mt-1 text-sm text-ink-muted">CSV or XLSX up to 10 MB</p>
            <label className="btn-primary mt-5 cursor-pointer">
              Choose File
              <input
                type="file"
                accept=".csv,.xlsx"
                className="hidden"
                onChange={(event) => onFileChosen(event.target.files?.[0] || null)}
              />
            </label>
          </div>

          {file ? (
            <div className="mt-4 flex items-center justify-between rounded-lg border border-surface-border px-4 py-3">
              <div className="flex items-center gap-3">
                <FileSpreadsheet className="h-5 w-5 text-ink-muted" />
                <div>
                  <p className="text-sm font-medium text-ink">{file.name}</p>
                  <p className="text-xs text-ink-subtle">
                    {(file.size / (1024 * 1024)).toFixed(2)} MB
                  </p>
                </div>
              </div>
              <button
                type="button"
                className="rounded-md p-1.5 text-ink-muted hover:bg-surface-muted"
                aria-label="Remove file"
                onClick={() => setFile(null)}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : null}

          <div className="mt-6 flex justify-end">
            <button
              type="button"
              className="btn-primary"
              disabled={!file || uploadMutation.isPending}
              onClick={() => file && uploadMutation.mutate(file)}
            >
              {uploadMutation.isPending ? "Uploading file…" : "Continue"}
            </button>
          </div>
        </div>
      ) : null}

      {step === 1 && upload ? (
        <div className="space-y-4">
          <div className="card p-5">
            <p className="text-sm text-ink-muted">
              File: <span className="font-medium text-ink">{upload.original_filename}</span>
            </p>
            <p className="mt-1 text-sm text-ink-muted">
              Rows: <span className="font-medium text-ink">{upload.total_rows.toLocaleString()}</span>
            </p>
            {upload.sheets.length > 1 ? (
              <div className="mt-3 max-w-xs">
                <label className="mb-1.5 block text-sm font-medium">Worksheet</label>
                <select
                  className="input"
                  value={sheet}
                  onChange={(event) => setSheet(event.target.value)}
                >
                  {upload.sheets.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}
          </div>

          {!emailMapped ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              Select which column contains email addresses.
            </div>
          ) : null}
          {mappingConflict ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              Each standard field can only be mapped once.
            </div>
          ) : null}

          <div className="card overflow-hidden">
            <div className="border-b border-surface-border px-4 py-3 text-sm font-medium">
              Column mapping
            </div>
            <div className="divide-y divide-surface-border">
              {upload.columns.map((column) => (
                <div
                  key={column}
                  className="grid gap-3 px-4 py-3 sm:grid-cols-2 sm:items-center"
                >
                  <p className="text-sm font-medium text-ink">{column}</p>
                  <select
                    aria-label={`Map ${column}`}
                    className="input"
                    value={mapping[column] || "ignore"}
                    onChange={(event) =>
                      updateMapping(column, event.target.value as MappingTarget)
                    }
                  >
                    {TARGET_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          </div>

          <div className="card overflow-x-auto">
            <div className="border-b border-surface-border px-4 py-3 text-sm font-medium">
              Preview (first {upload.preview_rows.length} rows)
            </div>
            <table className="min-w-full text-left text-sm">
              <thead className="bg-surface-muted/50 text-xs uppercase text-ink-subtle">
                <tr>
                  {upload.columns.map((column) => (
                    <th key={column} className="px-3 py-2 font-medium">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border">
                {upload.preview_rows.map((row, index) => (
                  <tr key={index}>
                    {upload.columns.map((column) => (
                      <td key={column} className="px-3 py-2 text-ink-muted">
                        {row[column] ?? "—"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-between">
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                if (upload) {
                  void cancelImport(upload.import_session_id).catch(() => undefined);
                }
                setStep(0);
                setUpload(null);
                setFile(null);
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={!emailMapped || mappingConflict || validateMutation.isPending}
              onClick={() => validateMutation.mutate()}
            >
              {validateMutation.isPending ? "Validating…" : "Validate"}
            </button>
          </div>
        </div>
      ) : null}

      {step === 2 && validation ? (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <StatCard label="Total" value={String(validation.total_rows)} icon={FileSpreadsheet} />
            <StatCard
              label="Importable"
              value={String(validation.importable_rows)}
              icon={CheckCircle2}
            />
            <StatCard
              label="Invalid Email"
              value={String(validation.invalid_email_rows)}
              icon={FileSpreadsheet}
            />
            <StatCard
              label="Missing Email"
              value={String(validation.missing_email_rows)}
              icon={FileSpreadsheet}
            />
            <StatCard
              label="Duplicates"
              value={String(validation.duplicate_in_file_rows)}
              icon={FileSpreadsheet}
            />
            <StatCard
              label="Already Existing"
              value={String(validation.duplicate_existing_rows)}
              icon={FileSpreadsheet}
            />
          </div>

          <div className="card overflow-hidden">
            <div className="flex flex-wrap gap-2 border-b border-surface-border px-4 py-3">
              {(
                [
                  ["invalid", "Invalid Emails"],
                  ["missing", "Missing Emails"],
                  ["duplicates", "Duplicates"],
                  ["existing", "Already Existing"],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  className={cn(
                    "rounded-full px-3 py-1 text-xs font-medium",
                    issueTab === key ? "bg-brand text-white" : "bg-surface-muted text-ink-muted",
                  )}
                  onClick={() => setIssueTab(key)}
                >
                  {label}
                </button>
              ))}
            </div>
            <IssueTable
              rows={
                issueTab === "invalid"
                  ? validation.sample_invalid_emails
                  : issueTab === "missing"
                    ? validation.sample_missing_emails
                    : issueTab === "duplicates"
                      ? validation.sample_duplicates_in_file
                      : validation.sample_duplicates_existing
              }
            />
          </div>

          <div className="flex justify-between">
            <button type="button" className="btn-secondary" onClick={() => setStep(1)}>
              Back
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={validation.importable_rows === 0}
              onClick={() => setStep(3)}
            >
              Continue to Review
            </button>
          </div>
          {validation.importable_rows === 0 ? (
            <p className="text-sm text-ink-muted">
              No valid contacts are available for import. Fix mapping or choose another file.
            </p>
          ) : null}
        </div>
      ) : null}

      {step === 3 && validation && upload ? (
        <div className="card space-y-5 p-6">
          <h2 className="text-base font-semibold text-ink">Ready to Import</h2>

          <div>
            <p className="mb-2 text-sm font-medium">Contact list</p>
            <div className="mb-3 flex gap-3">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  checked={listMode === "existing"}
                  onChange={() => setListMode("existing")}
                />
                Existing list
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  checked={listMode === "new"}
                  onChange={() => setListMode("new")}
                />
                Create new list
              </label>
            </div>
            {listMode === "existing" ? (
              <select
                className="input max-w-md"
                value={selectedListId}
                onChange={(event) => setSelectedListId(event.target.value)}
              >
                <option value="">Select a list</option>
                {(listsQuery.data || []).map((list) => (
                  <option key={list.id} value={list.id}>
                    {list.name}
                  </option>
                ))}
              </select>
            ) : (
              <div className="grid max-w-md gap-3">
                <input
                  className="input"
                  placeholder="List name"
                  value={newListName}
                  onChange={(event) => setNewListName(event.target.value)}
                />
                <textarea
                  className="input min-h-[80px]"
                  placeholder="Description (optional)"
                  value={newListDescription}
                  onChange={(event) => setNewListDescription(event.target.value)}
                />
              </div>
            )}
          </div>

          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-ink-muted">Total rows</dt>
              <dd className="font-medium">{validation.total_rows.toLocaleString()}</dd>
            </div>
            <div>
              <dt className="text-ink-muted">Will import</dt>
              <dd className="font-medium text-emerald-700">
                {validation.importable_rows.toLocaleString()}
              </dd>
            </div>
            <div>
              <dt className="text-ink-muted">Will skip</dt>
              <dd className="font-medium">{validation.skipped_rows.toLocaleString()}</dd>
            </div>
          </dl>

          <p className="text-sm text-ink-muted">
            Skipped because: Invalid email {validation.invalid_email_rows}, Missing email{" "}
            {validation.missing_email_rows}, Duplicate in file{" "}
            {validation.duplicate_in_file_rows}, Already exists{" "}
            {validation.duplicate_existing_rows}.
          </p>

          <div className="flex justify-between">
            <button type="button" className="btn-secondary" onClick={() => setStep(2)}>
              Back
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={
                !canContinueReview ||
                validation.importable_rows === 0 ||
                executeMutation.isPending
              }
              onClick={() => {
                // Re-validate against selected list before execute for accurate existing dups
                if (listMode === "existing" && selectedListId) {
                  validateImport(upload.import_session_id, {
                    column_mapping: mapping,
                    sheet: sheet || null,
                    contact_list_id: selectedListId,
                  })
                    .then((fresh) => {
                      setValidation(fresh);
                      if (fresh.importable_rows === 0) {
                        setError("No valid contacts are available for import.");
                        return;
                      }
                      executeMutation.mutate();
                    })
                    .catch((err) => setError(getErrorMessage(err)));
                } else {
                  executeMutation.mutate();
                }
              }}
            >
              {executeMutation.isPending
                ? "Importing…"
                : `Import ${validation.importable_rows.toLocaleString()} Contacts`}
            </button>
          </div>
        </div>
      ) : null}

      {step === 4 && result ? (
        <div className="card flex flex-col items-start gap-4 p-8">
          <CheckCircle2 className="h-10 w-10 text-emerald-600" />
          <div>
            <h2 className="text-xl font-semibold text-ink">Import Complete</h2>
            <p className="mt-2 text-sm text-ink-muted">
              {result.imported_rows.toLocaleString()} contacts imported.
            </p>
            <p className="text-sm text-ink-muted">
              {result.skipped_rows.toLocaleString()} rows skipped.
            </p>
            <p className="mt-1 text-sm text-ink-muted">
              List: {result.contact_list_name}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="btn-primary"
              onClick={() => navigate("/contacts")}
            >
              View Contacts
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setStep(0);
                setFile(null);
                setUpload(null);
                setValidation(null);
                setResult(null);
                setError(null);
                setMapping({});
              }}
            >
              Import Another File
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function IssueTable({
  rows,
}: {
  rows: ImportValidationResponse["sample_invalid_emails"];
}) {
  if (!rows.length) {
    return <p className="px-4 py-8 text-center text-sm text-ink-muted">No rows in this category.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-surface-muted/40 text-xs uppercase text-ink-subtle">
          <tr>
            <th className="px-4 py-2">Row</th>
            <th className="px-4 py-2">Email</th>
            <th className="px-4 py-2">Reason</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-border">
          {rows.map((row) => (
            <tr key={`${row.row_number}-${row.email}`}>
              <td className="px-4 py-2">{row.row_number}</td>
              <td className="px-4 py-2">{row.email || "—"}</td>
              <td className="px-4 py-2 text-ink-muted">{row.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
