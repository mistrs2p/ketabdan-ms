"use client";

import { useLocale, useTranslations } from "next-intl";
import { getEvents } from "@/lib/api";
import { useApiData } from "@/hooks/useApiData";
import { WeekCalendar } from "./WeekCalendar";
import { CalendarEmptyState } from "./CalendarEmptyState";
import { CalendarErrorState } from "./CalendarErrorState";
import { CalendarLoading } from "./CalendarLoading";
import { todayIsoDate, weekStartDowForLocale } from "./weekMath";

// The Calendar screen. A Client Component: the access token lives in
// browser localStorage, which a server component cannot read — a
// server-side fetch would go out unauthenticated and fail 401. All
// events are loaded once on mount (getEvents — backend ordering
// preserved) and handed to the WeekCalendar for week navigation and
// graphical rendering.
//
// "Today" and the locale's week-start weekday are computed only when
// the fetched data renders, which happens post-hydration in the
// browser — the user's own timezone, never the server's, so no
// hydration mismatch is possible.
export function CalendarPage() {
  const t = useTranslations("calendar");
  const tTitle = useTranslations("app.pages.calendar");
  const locale = useLocale();
  const state = useApiData(getEvents);

  return (
    <div className="flex w-full flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold">{tTitle("title")}</h1>
        <p className="text-muted-foreground">{t("description")}</p>
      </header>

      {state.status === "loading" ? <CalendarLoading /> : null}
      {state.status === "error" ? (
        <CalendarErrorState error={state.error} />
      ) : null}
      {state.status === "success" && state.data.length === 0 ? (
        <CalendarEmptyState />
      ) : null}
      {state.status === "success" && state.data.length > 0 ? (
        <WeekCalendar
          events={state.data}
          locale={locale}
          today={todayIsoDate()}
          weekStartDow={weekStartDowForLocale(locale)}
        />
      ) : null}
    </div>
  );
}
