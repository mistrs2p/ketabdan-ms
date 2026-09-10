import { setRequestLocale } from "next-intl/server";
import { CalendarPage } from "@/components/calendar/CalendarPage";

type Props = { params: Promise<{ locale: string }> };

// Live backend data — render per request, never at build time.
export const dynamic = "force-dynamic";

// Calendar — the primary graphical weekly scheduling screen (Phase 4).
// The shell, navigation, locale, direction, and theme all come from
// the existing app layout; this page only renders the calendar.
export default async function Page({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <CalendarPage locale={locale} />;
}
