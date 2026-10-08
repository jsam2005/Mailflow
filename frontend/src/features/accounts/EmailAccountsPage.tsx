import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Link2, Mail, RefreshCw, Settings2, Unplug } from "lucide-react";

import {
  connectGoogle,
  disconnectEmailAccount,
  fetchEmailAccounts,
  reconnectEmailAccount,
  sendTestEmail,
  testEmailAccountConnection,
  updateEmailAccount,
} from "@/api/emailAccounts";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PageHeader } from "@/components/PageHeader";
import { useToast } from "@/components/Toast";
import { AccountSettingsModal } from "@/features/accounts/AccountSettingsModal";
import { ConnectionStatusBadge } from "@/features/accounts/ConnectionStatusBadge";
import { SendTestEmailModal } from "@/features/accounts/SendTestEmailModal";
import type { EmailAccount, SendTestEmailPayload } from "@/types/emailAccounts";
import { getErrorMessage } from "@/utils/errors";

function formatChecked(value: string | null): string {
  if (!value) return "Never";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function EmailAccountsPage() {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const [settingsAccount, setSettingsAccount] = useState<EmailAccount | null>(null);
  const [testAccount, setTestAccount] = useState<EmailAccount | null>(null);
  const [disconnectAccount, setDisconnectAccount] = useState<EmailAccount | null>(null);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);

  const accountsQuery = useQuery({
    queryKey: ["email-accounts"],
    queryFn: fetchEmailAccounts,
  });

  useEffect(() => {
    const connected = searchParams.get("connected");
    const error = searchParams.get("error");
    if (connected === "1") {
      pushToast("Gmail account connected successfully.");
      setSearchParams({}, { replace: true });
      void queryClient.invalidateQueries({ queryKey: ["email-accounts"] });
    } else if (error) {
      pushToast("Could not connect Gmail. Please try again.", "error");
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams, pushToast, queryClient]);

  const connectMutation = useMutation({
    mutationFn: connectGoogle,
    onSuccess: (data) => {
      window.location.assign(data.authorization_url);
    },
    onError: (error) => pushToast(getErrorMessage(error), "error"),
  });

  const reconnectMutation = useMutation({
    mutationFn: (id: string) => reconnectEmailAccount(id),
    onSuccess: (data) => {
      window.location.assign(data.authorization_url);
    },
    onError: (error) => pushToast(getErrorMessage(error), "error"),
  });

  const settingsMutation = useMutation({
    mutationFn: ({
      id,
      values,
    }: {
      id: string;
      values: {
        daily_send_limit: number;
        hourly_send_limit: number;
        minimum_delay_seconds: number;
        maximum_delay_seconds: number;
      };
    }) => updateEmailAccount(id, values),
    onSuccess: async () => {
      setSettingsAccount(null);
      setSettingsError(null);
      pushToast("Account settings saved");
      await queryClient.invalidateQueries({ queryKey: ["email-accounts"] });
    },
    onError: (error) => setSettingsError(getErrorMessage(error)),
  });

  const disconnectMutation = useMutation({
    mutationFn: (id: string) => disconnectEmailAccount(id),
    onSuccess: async () => {
      setDisconnectAccount(null);
      pushToast("Gmail account disconnected");
      await queryClient.invalidateQueries({ queryKey: ["email-accounts"] });
    },
    onError: (error) => pushToast(getErrorMessage(error), "error"),
  });

  const sendMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: SendTestEmailPayload }) =>
      sendTestEmail(id, payload),
    onSuccess: (result) => {
      setTestAccount(null);
      setSendError(null);
      const extra = result.provider_message_id
        ? ` Message ID: ${result.provider_message_id}`
        : "";
      pushToast(`${result.message} Sent to ${result.to_email}.${extra}`);
      void queryClient.invalidateQueries({ queryKey: ["email-accounts"] });
    },
    onError: (error) => setSendError(getErrorMessage(error)),
  });

  const handleTestConnection = async (account: EmailAccount) => {
    setTestingId(account.id);
    try {
      const result = await testEmailAccountConnection(account.id);
      if (result.connected) {
        pushToast("Connection healthy");
      } else {
        pushToast(result.message || "Reconnect required", "error");
      }
      await queryClient.invalidateQueries({ queryKey: ["email-accounts"] });
    } catch (error) {
      pushToast(getErrorMessage(error), "error");
    } finally {
      setTestingId(null);
    }
  };

  const items = accountsQuery.data?.items ?? [];

  return (
    <div>
      <PageHeader
        title="Email Accounts"
        description="Connect and manage accounts used to send email."
        actions={
          <button
            type="button"
            className="btn-primary inline-flex items-center"
            onClick={() => connectMutation.mutate()}
            disabled={connectMutation.isPending}
          >
            <Mail className="mr-2 h-4 w-4" />
            {connectMutation.isPending ? "Connecting…" : "Connect Gmail"}
          </button>
        }
      />

      {accountsQuery.isLoading ? (
        <p className="text-sm text-ink-muted">Loading accounts…</p>
      ) : items.length === 0 ? (
        <div className="card flex flex-col items-start gap-4 p-8">
          <div className="rounded-lg bg-surface-muted p-3">
            <Mail className="h-6 w-6 text-ink-muted" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-ink">No email accounts connected</h2>
            <p className="mt-1 max-w-md text-sm text-ink-muted">
              Connect Gmail to send test emails and prepare for campaigns.
            </p>
          </div>
          <button
            type="button"
            className="btn-primary inline-flex items-center"
            onClick={() => connectMutation.mutate()}
            disabled={connectMutation.isPending}
          >
            Connect Gmail
          </button>
        </div>
      ) : (
        <div className="grid gap-4">
          {items.map((account) => (
            <article
              key={account.id}
              className="card flex flex-col gap-4 p-5 sm:flex-row sm:items-start sm:justify-between"
            >
              <div className="min-w-0 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center gap-1.5 rounded-md bg-surface-muted px-2 py-0.5 text-xs font-medium uppercase tracking-wide text-ink-muted">
                    <Mail className="h-3.5 w-3.5" />
                    {account.provider}
                  </span>
                  <ConnectionStatusBadge status={account.connection_status} />
                </div>
                <h2 className="truncate text-lg font-semibold text-ink">{account.email_address}</h2>
                {account.display_name ? (
                  <p className="text-sm text-ink-muted">{account.display_name}</p>
                ) : null}
                <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm text-ink-muted sm:grid-cols-3">
                  <div>
                    <dt className="text-ink-subtle">Sent today</dt>
                    <dd className="font-medium text-ink">{account.sent_today}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-subtle">Daily limit</dt>
                    <dd className="font-medium text-ink">{account.daily_send_limit}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-subtle">Last checked</dt>
                    <dd className="font-medium text-ink">
                      {formatChecked(account.last_connection_check_at)}
                    </dd>
                  </div>
                </dl>
                {account.last_connection_error && account.connection_status !== "connected" ? (
                  <p className="text-sm text-amber-800">{account.last_connection_error}</p>
                ) : null}
              </div>

              <div className="flex flex-wrap gap-2 sm:justify-end">
                <button
                  type="button"
                  className="btn-secondary inline-flex items-center"
                  onClick={() => void handleTestConnection(account)}
                  disabled={testingId === account.id || account.connection_status === "disconnected"}
                >
                  <RefreshCw
                    className={`mr-1.5 h-3.5 w-3.5 ${testingId === account.id ? "animate-spin" : ""}`}
                  />
                  {testingId === account.id ? "Testing…" : "Test Connection"}
                </button>
                <button
                  type="button"
                  className="btn-secondary inline-flex items-center"
                  onClick={() => {
                    setSendError(null);
                    setTestAccount(account);
                  }}
                  disabled={account.connection_status === "disconnected"}
                >
                  Send Test Email
                </button>
                <button
                  type="button"
                  className="btn-secondary inline-flex items-center"
                  onClick={() => {
                    setSettingsError(null);
                    setSettingsAccount(account);
                  }}
                >
                  <Settings2 className="mr-1.5 h-3.5 w-3.5" />
                  Settings
                </button>
                {(account.connection_status === "expired" ||
                  account.connection_status === "error" ||
                  account.connection_status === "disconnected") && (
                  <button
                    type="button"
                    className="btn-secondary inline-flex items-center"
                    onClick={() => reconnectMutation.mutate(account.id)}
                    disabled={reconnectMutation.isPending}
                  >
                    <Link2 className="mr-1.5 h-3.5 w-3.5" />
                    Reconnect Gmail
                  </button>
                )}
                {account.connection_status !== "disconnected" ? (
                  <button
                    type="button"
                    className="btn-secondary inline-flex items-center text-red-700"
                    onClick={() => setDisconnectAccount(account)}
                  >
                    <Unplug className="mr-1.5 h-3.5 w-3.5" />
                    Disconnect
                  </button>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      )}

      <AccountSettingsModal
        open={Boolean(settingsAccount)}
        account={settingsAccount}
        submitting={settingsMutation.isPending}
        serverError={settingsError}
        onClose={() => setSettingsAccount(null)}
        onSubmit={(values) => {
          if (!settingsAccount) return;
          settingsMutation.mutate({ id: settingsAccount.id, values });
        }}
      />

      <SendTestEmailModal
        open={Boolean(testAccount)}
        account={testAccount}
        submitting={sendMutation.isPending}
        serverError={sendError}
        onClose={() => setTestAccount(null)}
        onSubmit={(payload) => {
          if (!testAccount) return;
          sendMutation.mutate({ id: testAccount.id, payload });
        }}
      />

      <ConfirmDialog
        open={Boolean(disconnectAccount)}
        title="Disconnect Gmail account?"
        description={
          disconnectAccount
            ? `Account:\n${disconnectAccount.email_address}\n\nMailFlow will stop being able to send from this account.\nHistorical records will remain.`
            : ""
        }
        confirmLabel="Disconnect"
        destructive
        loading={disconnectMutation.isPending}
        onCancel={() => setDisconnectAccount(null)}
        onConfirm={() => {
          if (disconnectAccount) disconnectMutation.mutate(disconnectAccount.id);
        }}
      />
    </div>
  );
}
