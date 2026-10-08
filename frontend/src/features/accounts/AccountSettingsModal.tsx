import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Modal } from "@/components/Modal";
import type { EmailAccount } from "@/types/emailAccounts";

const schema = z
  .object({
    daily_send_limit: z.coerce.number().int().min(1).max(2000),
    hourly_send_limit: z.coerce.number().int().min(1).max(500),
    minimum_delay_seconds: z.coerce.number().int().min(1).max(3600),
    maximum_delay_seconds: z.coerce.number().int().min(1).max(7200),
  })
  .superRefine((values, ctx) => {
    if (values.hourly_send_limit > values.daily_send_limit) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Hourly limit cannot exceed daily limit",
        path: ["hourly_send_limit"],
      });
    }
    if (values.maximum_delay_seconds < values.minimum_delay_seconds) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Maximum delay must be ≥ minimum delay",
        path: ["maximum_delay_seconds"],
      });
    }
  });

export type AccountSettingsValues = z.infer<typeof schema>;

interface AccountSettingsModalProps {
  open: boolean;
  account: EmailAccount | null;
  submitting?: boolean;
  serverError?: string | null;
  onClose: () => void;
  onSubmit: (values: AccountSettingsValues) => Promise<void> | void;
}

export function AccountSettingsModal({
  open,
  account,
  submitting,
  serverError,
  onClose,
  onSubmit,
}: AccountSettingsModalProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AccountSettingsValues>({
    resolver: zodResolver(schema),
  });

  useEffect(() => {
    if (!open || !account) return;
    reset({
      daily_send_limit: account.daily_send_limit,
      hourly_send_limit: account.hourly_send_limit,
      minimum_delay_seconds: account.minimum_delay_seconds,
      maximum_delay_seconds: account.maximum_delay_seconds,
    });
  }, [open, account, reset]);

  return (
    <Modal
      open={open}
      title="Account settings"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </button>
          <button
            type="submit"
            form="account-settings-form"
            className="btn-primary"
            disabled={submitting}
          >
            {submitting ? "Saving…" : "Save"}
          </button>
        </>
      }
    >
      <p className="mb-4 text-sm text-ink-muted">
        These are safety limits configured inside MailFlow. They do not increase Gmail&apos;s own
        sending limits.
      </p>
      <form id="account-settings-form" className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
        <div>
          <label className="mb-1 block text-sm font-medium text-ink" htmlFor="daily_send_limit">
            Daily send limit
          </label>
          <input
            id="daily_send_limit"
            type="number"
            className="input"
            {...register("daily_send_limit")}
          />
          {errors.daily_send_limit ? (
            <p className="mt-1 text-xs text-red-600">{errors.daily_send_limit.message}</p>
          ) : null}
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-ink" htmlFor="hourly_send_limit">
            Hourly send limit
          </label>
          <input
            id="hourly_send_limit"
            type="number"
            className="input"
            {...register("hourly_send_limit")}
          />
          {errors.hourly_send_limit ? (
            <p className="mt-1 text-xs text-red-600">{errors.hourly_send_limit.message}</p>
          ) : null}
        </div>
        <div>
          <label
            className="mb-1 block text-sm font-medium text-ink"
            htmlFor="minimum_delay_seconds"
          >
            Minimum delay (seconds)
          </label>
          <input
            id="minimum_delay_seconds"
            type="number"
            className="input"
            {...register("minimum_delay_seconds")}
          />
          {errors.minimum_delay_seconds ? (
            <p className="mt-1 text-xs text-red-600">{errors.minimum_delay_seconds.message}</p>
          ) : null}
        </div>
        <div>
          <label
            className="mb-1 block text-sm font-medium text-ink"
            htmlFor="maximum_delay_seconds"
          >
            Maximum delay (seconds)
          </label>
          <input
            id="maximum_delay_seconds"
            type="number"
            className="input"
            {...register("maximum_delay_seconds")}
          />
          {errors.maximum_delay_seconds ? (
            <p className="mt-1 text-xs text-red-600">{errors.maximum_delay_seconds.message}</p>
          ) : null}
        </div>
        {serverError ? <p className="text-sm text-red-600">{serverError}</p> : null}
      </form>
    </Modal>
  );
}
