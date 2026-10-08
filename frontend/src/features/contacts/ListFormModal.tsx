import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Modal } from "@/components/Modal";
import type { ContactList } from "@/types/contacts";

const schema = z.object({
  name: z.string().min(1, "Name is required").max(255),
  description: z.string().max(5000).optional(),
});

export type ListFormValues = z.infer<typeof schema>;

interface ListFormModalProps {
  open: boolean;
  mode: "create" | "edit";
  initial?: ContactList | null;
  submitting?: boolean;
  serverError?: string | null;
  onClose: () => void;
  onSubmit: (values: ListFormValues) => Promise<void> | void;
}

export function ListFormModal({
  open,
  mode,
  initial,
  submitting,
  serverError,
  onClose,
  onSubmit,
}: ListFormModalProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ListFormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", description: "" },
  });

  useEffect(() => {
    if (!open) return;
    reset({
      name: initial?.name || "",
      description: initial?.description || "",
    });
  }, [open, initial, reset]);

  return (
    <Modal
      open={open}
      title={mode === "create" ? "New list" : "Edit list"}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </button>
          <button type="submit" form="list-form" className="btn-primary" disabled={submitting}>
            {submitting ? "Saving…" : mode === "create" ? "Create list" : "Save changes"}
          </button>
        </>
      }
    >
      <form
        id="list-form"
        className="space-y-4"
        onSubmit={handleSubmit(async (values) => onSubmit(values))}
        noValidate
      >
        <div>
          <label htmlFor="list-name" className="mb-1.5 block text-sm font-medium">
            Name
          </label>
          <input id="list-name" className="input" {...register("name")} />
          {errors.name && <p className="mt-1 text-sm text-red-600">{errors.name.message}</p>}
        </div>
        <div>
          <label htmlFor="list-description" className="mb-1.5 block text-sm font-medium">
            Description
          </label>
          <textarea
            id="list-description"
            className="input min-h-[96px]"
            {...register("description")}
          />
        </div>
        {serverError ? (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {serverError}
          </div>
        ) : null}
      </form>
    </Modal>
  );
}
