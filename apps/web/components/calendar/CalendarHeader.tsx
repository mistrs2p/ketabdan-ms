"use client";

import { useTranslations } from "next-intl";
import { addDays } from "./weekMath";

// Calendar toolbar: previous-week / today / next-week navigation plus
// the visible week's date range. The arrows flip visually in RTL
// (rtl:rotate-180) so "previous" always points toward the reading
// start — the SEMANTIC direction (earlier/later week) is identical in
// fa and en and can never be reversed by layout direction.
export function CalendarHeader({
  locale,
  weekStart,
  isCurrentWeek,
  onPrevious,
  onNext,
  onToday,
}: {
  locale: string;
  weekStart: Date;
  isCurrentWeek: boolean;
  onPrevious: () => void;
  onNext: () => void;
  onToday: () => void;
}) {
  const t = useTranslations("calendar");

  // UTC-anchored dates are formatted with timeZone "UTC" so the
  // displayed day matches the date arithmetic. The Gregorian calendar
  // is forced so the displayed dates stay on the same basis as the
  // underlying ISO data — the runtime fa locale would otherwise render
  // Persian-calendar day numbers (an implicit Jalali conversion this
  // task must not introduce). Weekday names stay localized.
  const rangeFormatter = new Intl.DateTimeFormat(
    locale.match(/^fa/) ? "fa-u-ca-gregory" : locale,
    {
      dateStyle: "medium",
      timeZone: "UTC",
    },
  );
  const weekEnd = addDays(weekStart, 6);
  const rangeLabel = `${rangeFormatter.format(weekStart)} – ${rangeFormatter.format(weekEnd)}`;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onPrevious}
          aria-label={t("prevWeek")}
          title={t("prevWeek")}
          className="rounded-lg border border-border bg-surface p-2 text-foreground hover:bg-primary/5"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className="h-4 w-4 rtl:rotate-180"
            aria-hidden="true"
          >
            <path d="m15 18-6-6 6-6" />
          </svg>
        </button>
        <button
          type="button"
          onClick={onToday}
          aria-label={t("today")}
          title={t("today")}
          disabled={isCurrentWeek}
          className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium text-foreground hover:bg-primary/5 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {t("today")}
        </button>
        <button
          type="button"
          onClick={onNext}
          aria-label={t("nextWeek")}
          title={t("nextWeek")}
          className="rounded-lg border border-border bg-surface p-2 text-foreground hover:bg-primary/5"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className="h-4 w-4 rtl:rotate-180"
            aria-hidden="true"
          >
            <path d="m9 18 6-6-6-6" />
          </svg>
        </button>
      </div>
      {/* aria-live keeps screen-reader users informed of the visible
          week when it changes. */}
      <p className="text-sm font-medium text-muted-foreground" aria-live="polite">
        {rangeLabel}
      </p>
    </div>
  );
}
