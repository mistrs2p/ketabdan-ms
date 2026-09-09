import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/routing";

// Not-found state for a valid event id with no matching event (GET
// /api/events/{event_id} → 404). The raw id is deliberately not shown
// as the primary message — a plain localized "event not found" with a
// way back to the Events list.
export async function EventNotFound() {
  const t = await getTranslations("events.detail.notFound");
  const tEvents = await getTranslations("app.pages.events");

  return (
    <div
      className="flex flex-col items-center gap-3 rounded-lg border border-border bg-surface p-10 text-center"
      role="alert"
    >
      <h2 className="text-lg font-bold">{t("title")}</h2>
      <p className="text-muted-foreground">{t("description")}</p>
      <Link
        href="/events"
        className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
      >
        {t("back", { page: tEvents("title") })}
      </Link>
    </div>
  );
}
