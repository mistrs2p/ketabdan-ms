import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/routing";

// Empty state for the Calendar (GET /api/events → []). The add CTA
// links to the Create Event flow — no empty seven-day grid shown.
export async function CalendarEmptyState() {
  const t = await getTranslations("calendar");

  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-border bg-surface p-10 text-center">
      <h2 className="text-lg font-bold">{t("empty.title")}</h2>
      <p className="text-muted-foreground">{t("empty.description")}</p>
      <Link
        href="/events/new"
        className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
      >
        {t("addEvent")}
      </Link>
    </div>
  );
}
