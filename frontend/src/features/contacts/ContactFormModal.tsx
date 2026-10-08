import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Modal } from "@/components/Modal";
import type { Contact, ContactList, ContactStatus } from "@/types/contacts";

const schema = z.object({
  contact_list_id: z.string().min(1, "Contact list is required"),
  email: z.string().email("Enter a valid email"),
  first_name: z.string().optional(),
  last_name: z.string().optional(),
  company: z.string().optional(),
  phone: z.string().optional(),
  website: z.string().optional(),
  status: z
    .enum(["active", "invalid", "unsubscribed", "bounced", "suppressed"])
    .optional(),
});

export type ContactFormValues = z.infer<typeof schema>;

interface ContactFormModalProps {
  open: boolean;
  mode: "create" | "edit";
  lists: ContactList[];
  initial?: Contact | null;
  defaultListId?: string;
  submitting?: boolean;
  serverError?: string | null;
  onClose: () => void;
  onSubmit: (values: ContactFormValues) => Promise<void> | void;
}

export function ContactFormModal({
  open,
  mode,
  lists,
  initial,
  defaultListId,
  submitting,
  serverError,
  onClose,
  onSubmit,
}: ContactFormModalProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ContactFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      contact_list_id: defaultListId || "",
      email: "",
      first_name: "",
      last_name: "",
      company: "",
      phone: "",
      website: "",
      status: "active",
    },
  });

  useEffect(() => {
    if (!open) return;
    if (mode === "edit" && initial) {
      reset({
        contact_list_id: initial.contact_list_id,
        email: initial.email,
        first_name: initial.first_name || "",
        last_name: initial.last_name || "",
        company: initial.company || "",
        phone: initial.phone || "",
        website: initial.website || "",
        status: initial.status,
      });
    } else {
      reset({
        contact_list_id: defaultListId || lists[0]?.id || "",
        email: "",
        first_name: "",
        last_name: "",
        company: "",
        phone: "",
        website: "",
        status: "active",
      });
    }
  }, [open, mode, initial, defaultListId, lists, reset]);

  return (
    <Modal
      open={open}
      title={mode === "create" ? "New contact" : "Edit contact"}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </button>
          <button
            type="submit"
            form="contact-form"
            className="btn-primary"
            disabled={submitting || lists.length === 0}
          >
            {submitting ? "Saving…" : mode === "create" ? "Create contact" : "Save changes"}
          </button>
        </>
      }
    >
      {lists.length === 0 ? (
        <p className="text-sm text-ink-muted">
          Create a contact list first before adding contacts.
        </p>
      ) : (
        <form
          id="contact-form"
          className="space-y-4"
          onSubmit={handleSubmit(async (values) => onSubmit(values))}
          noValidate
        >
          <div>
            <label htmlFor="contact_list_id" className="mb-1.5 block text-sm font-medium">
              Contact list
            </label>
            <select
              id="contact_list_id"
              className="input"
              disabled={mode === "edit"}
              {...register("contact_list_id")}
            >
              {lists.map((list) => (
                <option key={list.id} value={list.id}>
                  {list.name}
                </option>
              ))}
            </select>
            {errors.contact_list_id && (
              <p className="mt-1 text-sm text-red-600">{errors.contact_list_id.message}</p>
            )}
          </div>

          <div>
            <label htmlFor="email" className="mb-1.5 block text-sm font-medium">
              Email
            </label>
            <input id="email" type="email" className="input" {...register("email")} />
            {errors.email && <p className="mt-1 text-sm text-red-600">{errors.email.message}</p>}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="first_name" className="mb-1.5 block text-sm font-medium">
                First name
              </label>
              <input id="first_name" className="input" {...register("first_name")} />
            </div>
            <div>
              <label htmlFor="last_name" className="mb-1.5 block text-sm font-medium">
                Last name
              </label>
              <input id="last_name" className="input" {...register("last_name")} />
            </div>
          </div>

          <div>
            <label htmlFor="company" className="mb-1.5 block text-sm font-medium">
              Company
            </label>
            <input id="company" className="input" {...register("company")} />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="phone" className="mb-1.5 block text-sm font-medium">
                Phone
              </label>
              <input id="phone" className="input" {...register("phone")} />
            </div>
            <div>
              <label htmlFor="website" className="mb-1.5 block text-sm font-medium">
                Website
              </label>
              <input id="website" className="input" {...register("website")} />
            </div>
          </div>

          {mode === "edit" ? (
            <div>
              <label htmlFor="status" className="mb-1.5 block text-sm font-medium">
                Status
              </label>
              <select id="status" className="input" {...register("status")}>
                {(
                  [
                    "active",
                    "invalid",
                    "unsubscribed",
                    "bounced",
                    "suppressed",
                  ] as ContactStatus[]
                ).map((status) => (
                  <option key={status} value={status}>
                    {status.charAt(0).toUpperCase() + status.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          ) : null}

          {serverError ? (
            <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {serverError}
            </div>
          ) : null}
        </form>
      )}
    </Modal>
  );
}
