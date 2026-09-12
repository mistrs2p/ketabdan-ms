import { getTranslations, setRequestLocale } from "next-intl/server";
import type { Metadata } from "next";
import { DashboardPage } from "@/components/dashboard/DashboardPage";

type Props = { params: Promise<{ locale: string }> };

// The shell renders per request; the business data itself is fetched
// client-side (see DashboardPage) because the access token lives in
// browser localStorage.
export const dynamic = "force-dynamic";

// Tab title from the existing app.pages.dashboard.title message —
// no new translation keys.
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "app.pages.dashboard" });
  return { title: t("title") };
}

// The Dashboard. The page is a thin server shell (metadata + locale);
// DashboardPage fetches the three datasets (persons, events,
// event-assignments) in the browser, where the auth token lives, with
// independent failure handling per section.
export default async function Page({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <DashboardPage />;
}
