import { PageHeader } from "@/components/PageHeader";

interface PlaceholderPageProps {
  title: string;
  description: string;
  phase: string;
}

export function PlaceholderPage({ title, description, phase }: PlaceholderPageProps) {
  return (
    <div>
      <PageHeader title={title} description={description} />
      <div className="card flex min-h-[280px] flex-col items-center justify-center p-8 text-center">
        <p className="text-sm font-medium uppercase tracking-wide text-ink-subtle">
          Coming in {phase}
        </p>
        <p className="mt-2 max-w-md text-sm text-ink-muted">
          This section is scaffolded and ready for implementation. Core navigation and layout are
          available now.
        </p>
      </div>
    </div>
  );
}
