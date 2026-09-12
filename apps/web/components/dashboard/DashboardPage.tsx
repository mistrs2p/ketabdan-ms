"use client";

import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import {
  getPersons,
  getEvents,
  getEventAssignments,
  type EventAssignmentRead,
  type EventRead,
  type PersonRead,
} from "@/lib/api";
import { useApiData } from "@/hooks/useApiData";
import { useCalendarSystem } from "@/lib/calendar";
import { eventStatusLabel, formatEventDateTime } from "@/components/events/eventStatus";
import {
  buildDashboardEvents,
  buildDashboardPeople,
  countByStatus,
  type UpcomingEvent,
} from "./dashboardData";

// The Dashboard — the manager's fast operational view ("what needs
// attention"), not analytics. A Client Component: the access token
// lives in browser localStorage, which a server component cannot read
// — a server-side fetch would go out unauthenticated and fail 401.
// The three existing list endpoints (persons, events,
// event-assignments) are fetched once, in parallel, on mount and
// aggregated in memory by dashboardData (no dedicated dashboard
// endpoint exists and none is added). Each fetch fails independently
// — a failed dataset degrades only its own section with a localized
// unavailable state; the rest still renders.
export function DashboardPage() {
  const t = useTranslations("dashboard");
  const tTitle = useTranslations("app.pages.dashboard");
  const locale = useLocale();

  const peopleState = useApiData(getPersons);
  const eventsState = useApiData(getEvents);
  const assignmentsState = useApiData(getEventAssignments);

  const people: PersonRead[] | undefined =
    peopleState.status === "success" ? peopleState.data : undefined;
  const events: EventRead[] | undefined =
    eventsState.status === "success" ? eventsState.data : undefined;
  const assignments: EventAssignmentRead[] | undefined =
    assignmentsState.status === "success" ? assignmentsState.data : undefined;

  // Events + assignments together form the operational view. If
  // either fails, the event sections show their unavailable state; if
  // only assignments fail, metrics that need them are simply absent
  // (never fabricated).
  const dashboardEvents =
    events !== undefined && assignments !== undefined
      ? buildDashboardEvents(events, assignments)
      : undefined;
  const peopleOverview = people !== undefined ? buildDashboardPeople(people) : undefined;

  const loading =
    peopleState.status === "loading" &&
    eventsState.status === "loading" &&
    assignmentsState.status === "loading";

  if (loading) {
    return (
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-8">
        <header className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold">{tTitle("title")}</h1>
          <p className="text-muted-foreground">{t("description")}</p>
        </header>
        <p className="text-sm text-muted-foreground" role="status">
          {t("loading")}
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold">{tTitle("title")}</h1>
        <p className="text-muted-foreground">{t("description")}</p>
      </header>

      {/* Summary metrics — only what the loaded data actually supports */}
      <MetricsSection
        people={peopleOverview}
        events={events}
        dashboardEvents={dashboardEvents}
      />

      {/* Exceptions first: events with zero assignments */}
      {dashboardEvents ? (
        <UnassignedEventsSection
          unassigned={dashboardEvents.unassigned}
          locale={locale}
        />
      ) : (
        <SectionUnavailable
          title={t("eventsError.title")}
          body={events !== undefined
            ? t("assignmentsError.server")
            : t("eventsError.server")}
        />
      )}

      <UpcomingEventsSection
        upcoming={dashboardEvents?.upcoming ?? []}
        available={dashboardEvents !== undefined}
        locale={locale}
      />

      <StatusSnapshotSection events={events} />

      <PeopleSection people={peopleOverview} />

      <ActionsSection />
    </div>
  );
}

// --- Summary metrics -------------------------------------------------

function MetricsSection({
  people,
  events,
  dashboardEvents,
}: {
  people: ReturnType<typeof buildDashboardPeople> | undefined;
  events: EventRead[] | undefined;
  dashboardEvents: ReturnType<typeof buildDashboardEvents> | undefined;
}) {
  const t = useTranslations("dashboard.metrics");
  const cards: { label: string; value: string | number; error?: boolean }[] = [];

  if (people) {
    cards.push({ label: t("totalPeople"), value: people.total });
    cards.push({ label: t("activePeople"), value: people.active });
  }
  if (events) {
    cards.push({ label: t("upcomingEvents"), value: dashboardEvents ? dashboardEvents.upcoming.length : "—" });
  }
  if (dashboardEvents) {
    cards.push({ label: t("eventsWithAssignments"), value: dashboardEvents.assigned.length });
    cards.push({ label: t("eventsWithoutAssignments"), value: dashboardEvents.unassigned.length });
    cards.push({ label: t("totalAssignments"), value: dashboardEvents.assignmentCount });
  }

  if (cards.length === 0) {
    // People AND events both failed — nothing countable remains.
    return null;
  }

  return (
    <section aria-label={t("sectionLabel")} className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {cards.map((card) => (
        <div
          key={card.label}
          className="flex flex-col gap-1 rounded-lg border border-border bg-surface p-4"
        >
          <span className="text-xs font-medium text-muted-foreground">{card.label}</span>
          <span className="text-2xl font-bold tabular-nums">{card.value}</span>
        </div>
      ))}
    </section>
  );
}

// --- Unassigned events (the operational exception) --------------------

function UnassignedEventsSection({
  unassigned,
  locale,
}: {
  unassigned: EventRead[];
  locale: string;
}) {
  const t = useTranslations("dashboard.unassigned");
  const tStatus = useTranslations("events.status");
  const { system: calendarSystem } = useCalendarSystem();
  const statusLabels: Record<string, string> = {
    DRAFT: tStatus("DRAFT"),
    SCHEDULED: tStatus("SCHEDULED"),
    IN_PROGRESS: tStatus("IN_PROGRESS"),
    COMPLETED: tStatus("COMPLETED"),
    CANCELLED: tStatus("CANCELLED"),
  };

  return (
    <section aria-labelledby="dashboard-unassigned-heading" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="dashboard-unassigned-heading" className="text-lg font-bold">
          {t("title")}
        </h2>
        <p className="text-sm text-muted-foreground">{t("description")}</p>
      </div>
      {unassigned.length === 0 ? (
        <div
          className="flex flex-col gap-1 rounded-lg border border-dashed border-border bg-surface p-6 text-center"
          role="status"
        >
          <p className="text-sm font-medium">{t("empty.title")}</p>
          <p className="text-sm text-muted-foreground">{t("empty.description")}</p>
        </div>
      ) : (
        <ul className="flex flex-col gap-3">
          {unassigned.map((event) => (
            <li key={event.id}>
              <Link
                href={`/events/${event.id}`}
                className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface p-4 hover:bg-primary/5 sm:flex-row sm:items-center sm:justify-between sm:gap-4"
              >
                <span className="flex min-w-0 flex-col gap-0.5">
                  <span className="truncate text-sm font-medium">{event.title}</span>
                  <span className="text-xs text-muted-foreground">
                    {formatEventDateTime(event.planned_at, locale, calendarSystem)}
                  </span>
                </span>
                <span className="inline-flex w-fit items-center rounded bg-primary/10 px-2 py-0.5 text-xs text-primary">
                  {eventStatusLabel(event.status, statusLabels)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// --- Upcoming events --------------------------------------------------

function UpcomingEventsSection({
  upcoming,
  available,
  locale,
}: {
  upcoming: UpcomingEvent[];
  available: boolean;
  locale: string;
}) {
  const t = useTranslations("dashboard.upcoming");
  const tStatus = useTranslations("events.status");
  const { system: calendarSystem } = useCalendarSystem();
  const statusLabels: Record<string, string> = {
    DRAFT: tStatus("DRAFT"),
    SCHEDULED: tStatus("SCHEDULED"),
    IN_PROGRESS: tStatus("IN_PROGRESS"),
    COMPLETED: tStatus("COMPLETED"),
    CANCELLED: tStatus("CANCELLED"),
  };

  if (!available) {
    return (
      <section aria-labelledby="dashboard-upcoming-heading" className="flex flex-col gap-3">
        <h2 id="dashboard-upcoming-heading" className="text-lg font-bold">
          {t("title")}
        </h2>
        <SectionUnavailable title={t("error.title")} body={t("error.server")} inline={false} />
      </section>
    );
  }

  const limited = upcoming.slice(0, 5);

  return (
    <section aria-labelledby="dashboard-upcoming-heading" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="dashboard-upcoming-heading" className="text-lg font-bold">
          {t("title")}
        </h2>
        <p className="text-sm text-muted-foreground">{t("description")}</p>
      </div>
      {limited.length === 0 ? (
        <div
          className="flex flex-col gap-1 rounded-lg border border-dashed border-border bg-surface p-6 text-center"
          role="status"
        >
          <p className="text-sm font-medium">{t("empty.title")}</p>
          <p className="text-sm text-muted-foreground">{t("empty.description")}</p>
        </div>
      ) : (
        <ul className="flex flex-col gap-3">
          {limited.map(({ event, assignmentCount }) => (
            <li key={event.id}>
              <Link
                href={`/events/${event.id}`}
                className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface p-4 hover:bg-primary/5 sm:flex-row sm:items-center sm:justify-between sm:gap-4"
              >
                <span className="flex min-w-0 flex-col gap-0.5">
                  <span className="truncate text-sm font-medium">{event.title}</span>
                  <span className="text-xs text-muted-foreground">
                    {event.type} · {formatEventDateTime(event.planned_at, locale, calendarSystem)}
                  </span>
                </span>
                <span className="flex w-fit items-center gap-2">
                  {/* Assignment presence is a count, not a quality judgment */}
                  <span className="text-xs text-muted-foreground">
                    {t("assignmentCount", { count: assignmentCount })}
                  </span>
                  <span className="inline-flex items-center rounded bg-primary/10 px-2 py-0.5 text-xs text-primary">
                    {eventStatusLabel(event.status, statusLabels)}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// --- Event status snapshot ---------------------------------------------

function StatusSnapshotSection({
  events,
}: {
  events: EventRead[] | undefined;
}) {
  const t = useTranslations("dashboard.statusSnapshot");
  const tStatus = useTranslations("events.status");
  const statusLabels: Record<string, string> = {
    DRAFT: tStatus("DRAFT"),
    SCHEDULED: tStatus("SCHEDULED"),
    IN_PROGRESS: tStatus("IN_PROGRESS"),
    COMPLETED: tStatus("COMPLETED"),
    CANCELLED: tStatus("CANCELLED"),
  };

  if (events === undefined) {
    return null; // already reported in the metrics/unavailable sections
  }
  const counts = countByStatus(events);
  if (counts.length === 0) {
    return null; // no events at all — the upcoming-empty state says it
  }

  return (
    <section aria-labelledby="dashboard-status-heading" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="dashboard-status-heading" className="text-lg font-bold">
          {t("title")}
        </h2>
        <p className="text-sm text-muted-foreground">{t("description")}</p>
      </div>
      <ul className="flex flex-wrap gap-2">
        {counts.map(({ status, count }) => (
          <li
            key={status}
            className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm"
          >
            <span className="text-muted-foreground">
              {eventStatusLabel(status, statusLabels)}
            </span>
            <span className="font-bold tabular-nums">{count}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

// --- People overview ----------------------------------------------------

function PeopleSection({
  people,
}: {
  people: ReturnType<typeof buildDashboardPeople> | undefined;
}) {
  const t = useTranslations("dashboard.people");

  if (people === undefined) {
    return (
      <section aria-labelledby="dashboard-people-heading" className="flex flex-col gap-3">
        <h2 id="dashboard-people-heading" className="text-lg font-bold">
          {t("title")}
        </h2>
        <SectionUnavailable title={t("error.title")} body={t("error.server")} inline={false} />
      </section>
    );
  }

  return (
    <section aria-labelledby="dashboard-people-heading" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="dashboard-people-heading" className="text-lg font-bold">
          {t("title")}
        </h2>
        <p className="text-sm text-muted-foreground">{t("description")}</p>
      </div>
      <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4 sm:flex-row sm:gap-6">
        <dl className="flex gap-6">
          <div className="flex flex-col gap-0.5">
            <dt className="text-xs font-medium text-muted-foreground">{t("total")}</dt>
            <dd className="text-xl font-bold tabular-nums">{people.total}</dd>
          </div>
          <div className="flex flex-col gap-0.5">
            <dt className="text-xs font-medium text-muted-foreground">{t("active")}</dt>
            <dd className="text-xl font-bold tabular-nums">{people.active}</dd>
          </div>
          <div className="flex flex-col gap-0.5">
            <dt className="text-xs font-medium text-muted-foreground">{t("inactive")}</dt>
            <dd className="text-xl font-bold tabular-nums">{people.inactive}</dd>
          </div>
        </dl>
        {people.roleCounts.length > 0 ? (
          <dl className="flex min-w-0 flex-1 flex-wrap gap-2 sm:justify-end">
            {people.roleCounts.map(({ code, name, count }) => (
              <div
                key={code}
                className="flex items-center gap-1.5 rounded bg-primary/10 px-2 py-0.5 text-xs text-primary"
              >
                <dt>{name}</dt>
                <dd className="font-bold tabular-nums">{count}</dd>
              </div>
            ))}
          </dl>
        ) : null}
      </div>
    </section>
  );
}

// --- Actions -------------------------------------------------------------

function ActionsSection() {
  const t = useTranslations("dashboard.actions");

  const actions = [
    { href: "/people", label: t("viewPeople"), primary: false },
    { href: "/people/new", label: t("createPerson"), primary: true },
    { href: "/events", label: t("viewEvents"), primary: false },
    { href: "/events/new", label: t("createEvent"), primary: true },
    { href: "/calendar", label: t("viewCalendar"), primary: false },
  ];

  return (
    <section aria-label={t("sectionLabel")} className="flex flex-wrap gap-3">
      {actions.map((action) => (
        <Link
          key={action.href}
          href={action.href}
          className={
            action.primary
              ? "rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
              : "rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-primary/5"
          }
        >
          {action.label}
        </Link>
      ))}
    </section>
  );
}

// --- Shared unavailable state ---------------------------------------------

function SectionUnavailable({
  title,
  body,
  inline = true,
}: {
  title: string;
  body: string;
  inline?: boolean;
}) {
  return (
    <div
      className={`flex flex-col gap-1 rounded-lg border border-border ${inline ? "bg-surface" : ""} p-5`}
      role="alert"
    >
      <h2 className="text-sm font-bold">{title}</h2>
      <p className="text-sm text-muted-foreground">{body}</p>
    </div>
  );
}
