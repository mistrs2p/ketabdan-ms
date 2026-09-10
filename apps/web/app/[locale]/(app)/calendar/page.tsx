import { getTranslations, setRequestLocale } from "next-intl/server";
import type { Metadata } from "next";
import { CalendarPage } from "@/components/calendar/CalendarPage";

type Props = { params: Promise<{ locale: string }> };

// Live backend data — render per request, never at build time.
export const dynamic = "force-dynamic";

// Tab title from the existing app.pages.calendar.title message.
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "app.pages.calendar" });
  return { title: t("title") };
}

// Calendar — the primary graphical weekly scheduling screen (Phase 4).
// The shell, navigation, locale, direction, and theme all come from
// the existing app layout; this page only renders the calendar.
export default async function Page({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <CalendarPage locale={locale} />;
}
