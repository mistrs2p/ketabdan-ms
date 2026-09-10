"use client";

import { useState } from "react";
import type { EventRead } from "@/lib/api";
import { parseIsoDate, addDays, startOfWeek, toUtcDate } from "./weekMath";
import { CalendarHeader } from "./CalendarHeader";
import { CalendarGrid } from "./CalendarGrid";

// Interactive weekly calendar. Owns the visible-week state (as a day
// offset from the current week — default 0, i.e. the week containing
// "today", which the server passes in). Navigation semantics are
// temporal (previous/next week, today), never left/right — the arrows
// are direction-aware purely visually, so RTL cannot reverse them.
export function WeekCalendar({
  events,
  locale,
  today,
  weekStartDow,
}: {
  events: EventRead[];
  locale: string;
  today: string;
  weekStartDow: number;
}) {
  const [weekOffset, setWeekOffset] = useState(0);

  const todayParts = parseIsoDate(today);
  const todayDate = todayParts
    ? toUtcDate(todayParts)
    : toUtcDate({ year: 2026, month: 1, day: 1 });
  const weekStart = startOfWeek(
    addDays(todayDate, weekOffset * 7),
    weekStartDow,
  );

  return (
    <div className="flex w-full flex-col gap-3">
      <CalendarHeader
        locale={locale}
        weekStart={weekStart}
        isCurrentWeek={weekOffset === 0}
        onPrevious={() => setWeekOffset((offset) => offset - 1)}
        onNext={() => setWeekOffset((offset) => offset + 1)}
        onToday={() => setWeekOffset(0)}
      />
      <CalendarGrid
        events={events}
        locale={locale}
        today={today}
        weekStart={weekStart}
      />
    </div>
  );
}
