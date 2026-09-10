import { getLocale, getTranslations, setRequestLocale } from "next-intl/server";
import type { Metadata } from "next";
import { DashboardPage } from "@/components/dashboard/DashboardPage";

type Props = { params: Promise<{ locale: string }> };

// Live backend data — render per request, never at build time.
export const dynamic = "force-dynamic";

// Tab title from the existing app.pages.dashboard.title message —
// no new translation keys.
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "app.pages.dashboard" });
  return { title: t("title") };
}

// The Dashboard. Replaces the former placeholder. The page only
// resolves the locale; data loading and section rendering live in
// the DashboardPage server component (three parallel API calls,
// independent failure handling).
export default async function Page({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);
  const resolved = await getLocale();

  return <DashboardPage locale={resolved} />;
}
