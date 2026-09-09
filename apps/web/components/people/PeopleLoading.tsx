import { getTranslations } from "next-intl/server";

// Loading skeleton for the People list (shown via loading.tsx while the
// page's server component fetches). Mirrors the table layout so the
// transition is calm; text makes the state explicit without color cues.
export async function PeopleLoading() {
  const t = await getTranslations("people");

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
