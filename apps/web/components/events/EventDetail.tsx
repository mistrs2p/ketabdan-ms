import { getTranslations, getLocale } from "next-intl/server";
import { Link } from "@/i18n/routing";
import type { EventRead } from "@/lib/api";
import { eventStatusLabel, formatEventDateTime } from "./eventStatus";

// Event detail screen. Minimal and read-only: the four business fields
// of the EventRead contract, formatted for presentation only (the
// instant and its offset are never changed). No edit, no delete, no
// status controls — transitions are TBD-D7 and out of scope.
export async function EventDetail({ event }: { event: EventRead }) {
  const t = await getTranslations("events.detail");
  const tStatus = await getTranslations("events.status");
  const tEvents = await getTranslations("app.pages.events");
  const locale = await getLocale();

  const statusLabels: Record<string, string> = {
    DRAFT: tStatus("DRAFT"),
    SCHEDULED: tStatus("SCHEDULED"),
    IN_PROGRESS: tStatus("IN_PROGRESS"),
    COMPLETED: tStatus("COMPLETED"),
    CANCELLED: tStatus("CANCELLED"),
  };

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold">{event.title}</h1>
        <p className="text-muted-foreground">{t("description")}</p>
      </header>

      <dl className="flex flex-col divide-y divide-border rounded-lg border border-border bg-surface">
        <div className="flex flex-col gap-1 p-4 sm:flex-row sm:items-baseline sm:gap-4">
          <dt className="w-40 shrink-0 text-sm font-medium text-muted-foreground">
            {t("title")}
          </dt>
          <dd className="text-sm">{event.title}</dd>
        </div>
        <div className="flex flex-col gap-1 p-4 sm:flex-row sm:items-baseline sm:gap-4">
          <dt className="w-40 shrink-0 text-sm font-medium text-muted-foreground">
            {t("type")}
          </dt>
          <dd className="text-sm">{event.type}</dd>
        </div>
        <div className="flex flex-col gap-1 p-4 sm:flex-row sm:items-baseline sm:gap-4">
          <dt className="w-40 shrink-0 text-sm font-medium text-muted-foreground">
            {t("plannedAt")}
          </dt>
          <dd className="text-sm">
            {formatEventDateTime(event.planned_at, locale)}
          </dd>
        </div>
        <div className="flex flex-col gap-1 p-4 sm:flex-row sm:items-baseline sm:gap-4">
          <dt className="w-40 shrink-0 text-sm font-medium text-muted-foreground">
            {t("status")}
          </dt>
          <dd className="text-sm">
            <span className="inline-flex items-center rounded bg-primary/10 px-2 py-0.5 text-xs text-primary">
              {/* Status is carried by the localized text label; the
                  backend value is preserved, unknown values show raw. */}
              {eventStatusLabel(event.status, statusLabels)}
            </span>
          </dd>
        </div>
      </dl>

      <div>
        <Link
          href="/events"
          className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-primary/5"
        >
          {t("back", { page: tEvents("title") })}
        </Link>
      </div>
    </div>
  );
}

// Single-event fetch failure (GET /api/events/{id} failed on network
// or server). Not-found is handled separately by the page.
export async function EventDataError() {
  const t = await getTranslations("events.detail.error");

  return (
    <div
      className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-6"
      role="alert"
    >
      <h2 className="text-lg font-bold">{t("title")}</h2>
      <p className="text-muted-foreground">{t("server")}</p>
      <Link
        href="/events"
        className="text-sm font-medium text-primary hover:underline"
      >
        {t("back")}
      </Link>
    </div>
  );
}
