"use client";

import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import type {
  EventAssignmentRead,
  EventRead,
  PersonRead,
} from "@/lib/api";
import { eventStatusLabel, formatEventDateTime } from "./eventStatus";
import { EventAssignments } from "./EventAssignments";

// Event detail screen. The four business fields of the EventRead
// contract are formatted for presentation only (the instant and its
// offset are never changed), followed by the assignments section
// (EventAssignments — interactive, client-side). No edit, no delete,
// no status controls — transitions are TBD-D7 and out of scope.
//
// `people` feeds the assignment form's person selector;
// `initialAssignments` seeds the list so the first render is complete
// without an extra fetch. Either being undefined means its fetch
// failed — the section degrades to a localized error state while the
// event information stays readable. The raw event id is not shown —
// it is in the URL, and exposing it visually adds nothing.
export function EventDetail({
  event,
  initialAssignments,
  people,
}: {
  event: EventRead;
  initialAssignments: EventAssignmentRead[] | undefined;
  people: PersonRead[] | undefined;
}) {
  const t = useTranslations("events.detail");
  const tStatus = useTranslations("events.status");
  const tEvents = useTranslations("app.pages.events");
  const tError = useTranslations("events.assignments");
  const locale = useLocale();

  const statusLabels: Record<string, string> = {
    DRAFT: tStatus("DRAFT"),
    SCHEDULED: tStatus("SCHEDULED"),
    IN_PROGRESS: tStatus("IN_PROGRESS"),
    COMPLETED: tStatus("COMPLETED"),
    CANCELLED: tStatus("CANCELLED"),
  };

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold">{event.title}</h1>
        <p className="text-muted-foreground">{t("description")}</p>
      </header>

      <dl className="flex flex-col divide-y divide-border rounded-lg border border-border bg-surface sm:flex-row sm:divide-y-0 sm:divide-x sm:rtl:divide-x-reverse">
        <div className="flex flex-1 flex-col gap-1 p-4">
          <dt className="text-xs font-medium uppercase text-muted-foreground">
            {t("type")}
          </dt>
          <dd className="text-sm">{event.type}</dd>
        </div>
        <div className="flex flex-1 flex-col gap-1 p-4">
          <dt className="text-xs font-medium uppercase text-muted-foreground">
            {t("plannedAt")}
          </dt>
          <dd className="text-sm">
            {formatEventDateTime(event.planned_at, locale)}
          </dd>
        </div>
        <div className="flex flex-1 flex-col gap-1 p-4">
          <dt className="text-xs font-medium uppercase text-muted-foreground">
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

      {initialAssignments === undefined ? (
        <SectionError title={tError("error.title")} body={tError("error.server")} />
      ) : people === undefined ? (
        // The assignment list may be readable, but the form's person
        // selector cannot be built without real person data — say so,
        // in place, rather than rendering a broken form.
        <SectionError
          title={tError("peopleError.title")}
          body={tError("peopleError.server")}
        />
      ) : (
        <EventAssignments
          eventId={event.id}
          initialAssignments={initialAssignments}
          people={people}
        />
      )}

      <div>
        <Link
          href="/events"
          className="rounded-lg border border-border px-3 py-2 text-sm font-medium text-foreground hover:bg-primary/5"
        >
          {t("back", { page: tEvents("title") })}
        </Link>
      </div>
    </div>
  );
}

// Section-level load failure (assignments or people fetch failed).
// The rest of the event detail stays readable.
function SectionError({ title, body }: { title: string; body: string }) {
  return (
    <div
      className="flex flex-col gap-1 rounded-lg border border-border bg-surface p-5"
      role="alert"
    >
      <h2 className="text-sm font-bold">{title}</h2>
      <p className="text-sm text-muted-foreground">{body}</p>
    </div>
  );
}

// Single-event fetch failure (GET /api/events/{id} failed on network
// or server). Not-found is handled separately by the loader.
export function EventDataError() {
  const t = useTranslations("events.detail.error");

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
