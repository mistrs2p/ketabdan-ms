import { getTranslations } from "next-intl/server";

// Streaming loading UI for the dashboard route — shown while the
// page's server component awaits its three API calls. Mirrors the
// section layout (metric row + list skeletons) so the transition is
// calm.
export default async function Loading() {
  const t = await getTranslations("dashboard");

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-8" role="status" aria-label={t("loading")}>
      <div className="flex flex-col gap-2">
        <div className="h-8 w-48 animate-pulse rounded bg-surface" />
        <div className="h-4 w-72 animate-pulse rounded bg-surface" />
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="h-20 animate-pulse rounded-lg border border-border bg-surface" />
        ))}
      </div>
      <span className="text-sm text-muted-foreground">{t("loading")}</span>
      {Array.from({ length: 3 }, (_, i) => (
        <div key={i} className="h-16 animate-pulse rounded-lg border border-border bg-surface" />
      ))}
    </div>
  );
}
