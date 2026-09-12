"use client";

import { useLocale, useTranslations } from "next-intl";
import { getEvents, type EventRead } from "@/lib/api";
import { useApiData } from "@/hooks/useApiData";
import { Link } from "@/i18n/routing";
import { eventStatusLabel, formatEventDateTime } from "./eventStatus";
import { EventsErrorState } from "./EventsErrorState";
import { EventsEmptyState } from "./EventsEmptyState";
import { EventsLoading } from "./EventsLoading";

// The Events list screen, following the People list pattern. A Client
// Component: the access token lives in browser localStorage, which a
// server component cannot read — a server-side fetch would go out
// unauthenticated and fail 401. The list is therefore fetched on
// mount, after the AuthGate has confirmed the session (see
// hooks/useApiData).
//
// The typed API layer (getEvents) is called directly. Backend
// ordering (planned_at, then id) is preserved; the UI never re-sorts.
// planned_at is formatted for presentation only — the instant and
// offset are never changed.
export function EventsPage() {
  const t = useTranslations("events");
  const tTitle = useTranslations("app.pages.events");
  const locale = useLocale();
  const state = useApiData(getEvents);

  const statusLabels: Record<string, string> = {
    DRAFT: t("status.DRAFT"),
    SCHEDULED: t("status.SCHEDULED"),
    IN_PROGRESS: t("status.IN_PROGRESS"),
    COMPLETED: t("status.COMPLETED"),
    CANCELLED: t("status.CANCELLED"),
  };

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold">{tTitle("title")}</h1>
          <p className="text-muted-foreground">{t("description")}</p>
        </div>
        <Link
          href="/events/new"
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          {t("addEvent")}
        </Link>
      </header>

      {state.status === "loading" ? <EventsLoading /> : null}
      {state.status === "error" ? <EventsErrorState error={state.error} /> : null}
      {state.status === "success" && state.data.length === 0 ? (
        <EventsEmptyState />
      ) : null}
      {state.status === "success" && state.data.length > 0 ? (
        <EventsTable
          events={state.data}
          locale={locale}
          statusLabels={statusLabels}
        />
      ) : null}
    </div>
  );
}

// Events table. Desktop (≥ md): a semantic table. Below md: the same
// data as stacked cards. Status is text (not color-only). The View
// action links to the event detail page via the localized routing
// helper.
function EventsTable({
  events,
  locale,
  statusLabels,
}: {
  events: EventRead[];
  locale: string;
  statusLabels: Record<string, string>;
}) {
  const t = useTranslations("events");

  return (
    <>
      {/* Desktop table */}
      <table className="hidden w-full border-collapse text-start text-sm md:table">
        <caption className="sr-only">{t("table.caption")}</caption>
        <thead>
          <tr className="border-b border-border text-start">
            <th scope="col" className="px-4 py-3 text-start font-medium">
              {t("table.title")}
            </th>
            <th scope="col" className="px-4 py-3 text-start font-medium">
              {t("table.type")}
            </th>
            <th scope="col" className="px-4 py-3 text-start font-medium">
              {t("table.plannedAt")}
            </th>
            <th scope="col" className="px-4 py-3 text-start font-medium">
              {t("table.status")}
            </th>
            <th scope="col" className="px-4 py-3 text-start font-medium">
              {t("table.actions")}
            </th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr key={event.id} className="border-b border-border last:border-b-0">
              <td className="px-4 py-3 font-medium">{event.title}</td>
              <td className="px-4 py-3 text-muted-foreground">{event.type}</td>
              <td className="px-4 py-3 text-muted-foreground">
                {formatEventDateTime(event.planned_at, locale)}
              </td>
              <td className="px-4 py-3">
                <StatusBadge
                  label={eventStatusLabel(event.status, statusLabels)}
                />
              </td>
              <td className="px-4 py-3">
                <ViewAction
                  eventId={event.id}
                  eventTitle={event.title}
                  label={t("viewAction")}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Mobile cards */}
      <ul className="flex flex-col gap-3 md:hidden">
        {events.map((event) => (
          <li
            key={event.id}
            className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-4"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="font-medium">{event.title}</span>
              <StatusBadge
                label={eventStatusLabel(event.status, statusLabels)}
              />
            </div>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
              <dt className="text-muted-foreground">{t("table.type")}</dt>
              <dd>{event.type}</dd>
              <dt className="text-muted-foreground">{t("table.plannedAt")}</dt>
              <dd>{formatEventDateTime(event.planned_at, locale)}</dd>
            </dl>
            <div>
              <ViewAction
                eventId={event.id}
                eventTitle={event.title}
                label={t("viewAction")}
              />
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}

function StatusBadge({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center rounded bg-primary/10 px-2 py-0.5 text-xs text-primary">
      {/* Status is carried by the localized text label. */}
      {label}
    </span>
  );
}

function ViewAction({
  eventId,
  eventTitle,
  label,
}: {
  eventId: string;
  eventTitle: string;
  label: string;
}) {
  return (
    <Link
      href={`/events/${eventId}`}
      aria-label={`${label}: ${eventTitle}`}
      className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-primary/5"
    >
      {label}
    </Link>
  );
}
