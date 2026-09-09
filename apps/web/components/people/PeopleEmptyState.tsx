import { getTranslations } from "next-intl/server";

// Empty state for the People list (GET /api/persons → []). The add
// CTA stays visual only — creation is a later task and the button
// carries a title explaining that.
export async function PeopleEmptyState() {
  const t = await getTranslations("people");

  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-border bg-surface p-10 text-center">
      <h2 className="text-lg font-bold">{t("empty.title")}</h2>
      <p className="text-muted-foreground">{t("empty.description")}</p>
    </div>
  );
}
