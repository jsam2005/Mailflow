import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  MailCheck,
  MessageSquareReply,
  Send,
  Users,
} from "lucide-react";

import { fetchCampaigns } from "@/api/campaigns";
import { fetchContactStats } from "@/api/contacts";
import { fetchEmailAccounts } from "@/api/emailAccounts";
import { fetchTemplates } from "@/api/templates";
import { PageHeader } from "@/components/PageHeader";
import { StatCard } from "@/components/StatCard";

export function DashboardPage() {
  const contactsQuery = useQuery({
    queryKey: ["contact-stats"],
    queryFn: fetchContactStats,
  });
  const campaignsQuery = useQuery({
    queryKey: ["campaigns-dashboard"],
    queryFn: () => fetchCampaigns({ page: 1, page_size: 5, search: "", status: "", sort_by: "updated_at", sort_order: "desc" }),
  });
  const templatesQuery = useQuery({
    queryKey: ["templates-dashboard"],
    queryFn: () =>
      fetchTemplates({
        page: 1,
        page_size: 1,
        search: "",
        sort_by: "updated_at",
        sort_order: "desc",
      }),
  });
  const accountsQuery = useQuery({
    queryKey: ["email-accounts"],
    queryFn: fetchEmailAccounts,
  });

  const totalContacts = contactsQuery.data?.total ?? 0;
  const campaigns = campaignsQuery.data?.items ?? [];
  const sentToday = campaigns.reduce((sum, c) => sum + (c.stats?.messages_sent ?? c.stats?.sent ?? 0), 0);
  const queued = campaigns.reduce((sum, c) => sum + (c.stats?.messages_queued ?? c.stats?.queued ?? 0), 0);
  const failed = campaigns.reduce((sum, c) => sum + (c.stats?.messages_failed ?? c.stats?.failed ?? 0), 0);
  const connected = (accountsQuery.data?.items ?? []).filter((a) => a.connection_status === "connected").length;
  const templateTotal = templatesQuery.data?.total ?? 0;

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Live overview from your workspace. Empty means a clean account — start by connecting Gmail and importing contacts."
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <StatCard label="Contacts" value={String(totalContacts)} icon={Users} />
        <StatCard label="Campaign sent (listed)" value={String(sentToday)} icon={Send} />
        <StatCard label="Queued (listed)" value={String(queued)} icon={MailCheck} />
        <StatCard label="Failed (listed)" value={String(failed)} icon={AlertTriangle} />
        <StatCard label="Templates" value={String(templateTotal)} icon={MailCheck} />
        <StatCard
          label="Connected accounts"
          value={String(connected)}
          hint="Reply inbox arrives in a later phase"
          icon={MessageSquareReply}
        />
      </div>

      {!connected || totalContacts === 0 ? (
        <section className="card mt-6 space-y-3 p-5">
          <h2 className="text-sm font-semibold text-ink">Get started</h2>
          <ul className="list-disc space-y-1 pl-5 text-sm text-ink-muted">
            {!connected ? (
              <li>
                <Link className="text-sky-700 underline" to="/email-accounts">
                  Connect Gmail
                </Link>
              </li>
            ) : null}
            {totalContacts === 0 ? (
              <li>
                <Link className="text-sky-700 underline" to="/contacts/import">
                  Import contacts
                </Link>
              </li>
            ) : null}
            {templateTotal === 0 ? (
              <li>
                <Link className="text-sky-700 underline" to="/templates">
                  Create a template
                </Link>
              </li>
            ) : null}
            <li>
              <Link className="text-sky-700 underline" to="/campaigns/new">
                Create a campaign
              </Link>
            </li>
          </ul>
        </section>
      ) : null}

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <section className="card p-5">
          <h2 className="text-sm font-semibold text-ink">Recent campaigns</h2>
          {campaigns.length === 0 ? (
            <p className="mt-3 text-sm text-ink-muted">No campaigns yet.</p>
          ) : (
            <ul className="mt-3 space-y-2 text-sm">
              {campaigns.map((c) => (
                <li key={c.id}>
                  <Link className="font-medium text-ink hover:underline" to={`/campaigns/${c.id}`}>
                    {c.name}
                  </Link>
                  <span className="ml-2 text-ink-subtle">{c.status}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="card p-5">
          <h2 className="text-sm font-semibold text-ink">Replies</h2>
          <p className="mt-3 text-sm text-ink-muted">
            Inbox reply sync is not enabled in this phase. No reply data is shown.
          </p>
        </section>
      </div>
    </div>
  );
}
