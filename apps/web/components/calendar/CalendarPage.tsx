import { getTranslations } from "next-intl/server";
import { getEvents, ApiError, type EventRead } from "@/lib/api";
import { WeekCalendar } from "./WeekCalendar";
import { CalendarEmptyState } from "./CalendarEmptyState";
import { CalendarErrorState } from "./CalendarErrorState";
import { todayIsoDate, weekStartDowForLocale } from "./weekMath";

// The Calendar screen (server side). Loads all events once via the
// typed API layer (getEvents — backend ordering preserved) and hands
// them to the client WeekCalendar for week navigation and graphical
// rendering. "Today" and the locale's week-start weekday are computed
// here and passed as props, so the client's first render matches the
// server HTML regardless of timezone differences.
//
// States: loading via sibling loading.tsx (streaming), error / empty
// handled here, data in WeekCalendar.
export async function CalendarPage({ locale }: { locale: string }) {
  const t = await getTranslations("calendar");
  const tTitle = await getTranslations("app.pages.calendar");

  let events: EventRead[] = [];
  let error: ApiError | undefined;
  try {
    events = await getEvents();
  } catch (e) {
    if (e instanceof ApiError) {
      error = e;
    } else {
      error = new ApiError("server", String(e));
    }
  }

  return (
    <div className="flex w-full flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold">{tTitle("title")}</h1>
        <p className="text-muted-foreground">{t("description")}</p>
      </header>

      {error ? <CalendarErrorState error={error} /> : null}
      {!error && events.length === 0 ? <CalendarEmptyState /> : null}
      {!error && events.length > 0 ? (
        <WeekCalendar
          events={events}
          locale={locale}
          today={todayIsoDate()}
          weekStartDow={weekStartDowForLocale(locale)}
        />
      ) : null}
    </div>
  );
}
