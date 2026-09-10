"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import type { EventRead } from "@/lib/api";
import { addDays, isoOf } from "./weekMath";
import { CalendarEvent } from "./CalendarEvent";

// Visible time range (technical MVP choice, documented in the task
// report): 08:00–22:00 — a practical branch-activity window. Events
// outside it are clamped to the nearest grid edge and marked with an
// "outside visible hours" indicator rather than disappearing.
const GRID_START_HOUR = 8;
const GRID_END_HOUR = 22; // exclusive
const HOURS = GRID_END_HOUR - GRID_START_HOUR;
const HOUR_HEIGHT = 60; // px per hour — also the grid line spacing
const GRID_HEIGHT = HOURS * HOUR_HEIGHT;
// The backend model has NO duration field (docs/06 §4c) — events are
// point-in-time. Each event is a fixed-height block; this height is
// presentation, never persisted or interpreted as a duration.
const EVENT_HEIGHT = 48;

interface LaidOutEvent {
  event: EventRead;
  top: number;
  lane: number;
  outside: "before" | "after" | null;
  timeLabel: string;
}

// The weekly grid: a time column plus seven day columns. Day headers
// are sticky to the top of the scrollable body; the whole grid is
// horizontally scrollable on narrow screens (min-width keeps seven
// readable columns instead of squeezing them). Logical CSS (grid
// column order, inset-inline-start, border-s) makes RTL mirror
// naturally: in fa the week starts at the right edge, exactly where
// reading starts.
export function CalendarGrid({
  events,
  locale,
  today,
  weekStart,
}: {
  events: EventRead[];
  locale: string;
  today: string;
  weekStart: Date;
}) {
  const t = useTranslations("calendar");
  const tStatus = useTranslations("events.status");

  // Event bucketing uses the VIEWER's local timezone, which can differ
  // from the server's — positioning only after mount guarantees the
  // first client render matches the server HTML.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const statusLabels: Record<string, string> = {
    DRAFT: tStatus("DRAFT"),
    SCHEDULED: tStatus("SCHEDULED"),
    IN_PROGRESS: tStatus("IN_PROGRESS"),
    COMPLETED: tStatus("COMPLETED"),
    CANCELLED: tStatus("CANCELLED"),
  };

  const timeFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat(locale, {
        hour: "numeric",
        minute: "2-digit",
      }),
    [locale],
  );
  // Hour-gutter labels come from locally-constructed dates, so the
  // displayed hour is the intended one in any timezone.
  const hourLabels = useMemo(
    () =>
      Array.from({ length: HOURS }, (_, i) => {
        const hour = GRID_START_HOUR + i;
        return timeFormatter.format(new Date(2024, 0, 1, hour));
      }),
    [timeFormatter],
  );
  const dayFormatter = useMemo(
    () =>
      // Gregorian calendar forced for fa (fa-u-ca-gregory) so day
      // numbers stay on the ISO basis of the underlying data — the
      // runtime fa default is the Persian calendar, which would be an
      // implicit Jalali conversion this task must not introduce.
      // Weekday names stay localized. UTC anchored: the displayed day
      // matches the week arithmetic.
      new Intl.DateTimeFormat(
        locale.match(/^fa/) ? "fa-u-ca-gregory" : locale,
        {
          weekday: "short",
          day: "numeric",
          timeZone: "UTC",
        },
      ),
    [locale],
  );

  // Per-day layout: bucket events by local calendar day, convert the
  // start time to a pixel offset from grid start, clamp out-of-range
  // events to the grid edge, then assign overlap lanes greedily so
  // same/near-time events stack side by side instead of hiding each
  // other. All deterministic; backend ordering is preserved within a
  // day (same sort the backend guarantees).
  const days = useMemo(() => {
    const dayDates = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
    const layouts = dayDates.map((dayDate) => {
      const dayKey = isoOf(dayDate);
      const dayEvents: LaidOutEvent[] = [];
      if (mounted) {
        for (const event of events) {
          const date = new Date(event.planned_at);
          if (Number.isNaN(date.getTime())) continue; // unparseable: never crash the grid
          const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
          if (key !== dayKey) continue;

          const minutesSinceMidnight = date.getHours() * 60 + date.getMinutes();
          let top = minutesSinceMidnight - GRID_START_HOUR * 60;
          let outside: LaidOutEvent["outside"] = null;
          if (top < 0) {
            outside = "before";
            top = 0;
          }
          const maxTop = GRID_HEIGHT - EVENT_HEIGHT;
          if (top > maxTop) {
            outside = "after";
            top = maxTop;
          }
          dayEvents.push({
            event,
            top,
            lane: 0,
            outside,
            timeLabel: timeFormatter.format(date),
          });
        }
        // Backend order (planned_at, then id) preserved; equal times
        // tie-break deterministically by id.
        dayEvents.sort(
          (a, b) =>
            a.top - b.top || a.event.id.localeCompare(b.event.id),
        );
      }

      // Greedy lane packing: an event joins the first lane whose last
      // occupant ends (top + fixed height) at or before its top; a
      // collision opens a new lane. Lanes render side by side.
      const laneEnds: number[] = [];
      for (const item of dayEvents) {
        const end = item.top + EVENT_HEIGHT;
        let lane = laneEnds.findIndex((end_) => end_ <= item.top);
        if (lane === -1) {
          lane = laneEnds.length;
          laneEnds.push(end);
        } else {
          laneEnds[lane] = end;
        }
        item.lane = lane;
      }
      return { dayDate, dayKey, items: dayEvents, lanes: Math.max(1, laneEnds.length) };
    });
    return layouts;
  }, [events, weekStart, mounted, timeFormatter]);

  // `grid` is required alongside grid-cols-* — grid-cols only sets
  // grid-template-columns; without display:grid the cells stack as
  // full-width blocks instead of seven side-by-side day columns.
  const gridTemplate = "grid grid-cols-[4.5rem_repeat(7,minmax(0,1fr))]";
  const hourLineStyle = {
    height: GRID_HEIGHT,
    backgroundImage: `repeating-linear-gradient(to bottom, var(--color-border) 0px, var(--color-border) 1px, transparent 1px, transparent ${HOUR_HEIGHT}px)`,
  };

  return (
    <div
      className="max-h-[75vh] overflow-auto rounded-lg border border-border bg-surface"
      role="region"
      aria-label={t("calendarLabel")}
    >
      <div className="min-w-210">
        {/* Day header row — sticky to the top of the scrollable body. */}
        <div
          className={`sticky top-0 z-20 border-b border-border bg-surface text-xs ${gridTemplate}`}
        >
          <div aria-hidden="true" />
          {days.map(({ dayDate, dayKey }) => {
            const isToday = dayKey === today;
            return (
              <div
                key={dayKey}
                className={`border-s border-border p-2 text-center font-medium ${
                  isToday
                    ? // text-foreground for AA contrast on the primary/10
                      // tint (text-primary measured 4.49:1); the tint plus
                      // the textual Today badge carry the highlight, so
                      // color is never the only indicator.
                      "bg-primary/10 text-foreground"
                    : "text-muted-foreground"
                }`}
              >
                {dayFormatter.format(dayDate)}
                {isToday ? (
                  <span className="ms-1 rounded bg-primary/20 px-1 py-0.5">
                    {t("today")}
                  </span>
                ) : null}
              </div>
            );
          })}
        </div>

        {/* Body: time gutter + seven day columns. */}
        <div className={gridTemplate}>
          <div className="relative" style={{ height: GRID_HEIGHT }}>
            {hourLabels.map((label, i) => (
              <div
                key={label}
                className="flex h-15 items-start justify-end pe-2"
              >
                <span className="-mt-1 block text-[11px] text-muted-foreground">
                  {i === 0 ? "" : label}
                </span>
              </div>
            ))}
          </div>
          {days.map(({ dayDate, dayKey, items, lanes }) => {
            const isToday = dayKey === today;
            return (
              <div
                key={dayKey}
                className={`relative border-s border-border ${isToday ? "bg-primary/5" : ""}`}
                style={hourLineStyle}
                aria-label={dayFormatter.format(dayDate)}
              >
                {items.map((item) => (
                  <CalendarEvent
                    key={item.event.id}
                    event={item.event}
                    top={item.top}
                    lane={item.lane}
                    lanes={lanes}
                    outside={item.outside}
                    timeLabel={item.timeLabel}
                    statusLabel={statusLabels[item.event.status] ?? item.event.status}
                    outsideLabel={t("outsideHours")}
                  />
                ))}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
