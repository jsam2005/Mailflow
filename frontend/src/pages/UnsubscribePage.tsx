import { useMutation } from "@tanstack/react-query";
import axios from "axios";
import { useParams } from "react-router-dom";

import { getErrorMessage } from "@/utils/errors";

/** Public endpoint — avoid shared client 401 → login redirect. */
const publicClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "",
  timeout: 30000,
});

export function UnsubscribePage() {
  const { token } = useParams<{ token: string }>();

  const mutation = useMutation({
    mutationFn: async () => {
      const { data } = await publicClient.post<{ status: string; message: string }>(
        `/api/v1/public/unsubscribe/${token}`,
      );
      return data;
    },
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-muted px-4">
      <div className="card w-full max-w-md space-y-4 p-6 text-center">
        <h1 className="text-xl font-semibold text-ink">Unsubscribe</h1>
        {mutation.isSuccess ? (
          <p className="text-sm text-ink-muted">{mutation.data.message}</p>
        ) : (
          <>
            <p className="text-sm text-ink-muted">
              Confirm that you no longer want to receive campaign emails from this sender.
            </p>
            <button
              type="button"
              className="btn-primary w-full"
              disabled={!token || mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending ? "Working…" : "Confirm unsubscribe"}
            </button>
            {mutation.isError ? (
              <p className="text-sm text-red-600">{getErrorMessage(mutation.error)}</p>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
