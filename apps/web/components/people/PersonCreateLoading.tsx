import { getTranslations } from "next-intl/server";

// Loading UI for the Create Person route — shown while the page's
// server component fetches the role reference data (GET /api/roles).
export async function PersonCreateLoading() {
  const t = await getTranslations("people.create");

  return (
    <div
      className="flex flex-col gap-3"
      role="status"
      aria-label={t("loading")}
    >
      <span className="text-sm text-muted-foreground">{t("loading")}</span>
      {Array.from({ length: 4 }, (_, i) => (
        <div
          key={i}
          className="h-14 animate-pulse rounded-lg border border-border bg-surface"
        />
      ))}
    </div>
  );
}
