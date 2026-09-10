import { getLocale, setRequestLocale } from "next-intl/server";
import { DashboardPage } from "@/components/dashboard/DashboardPage";

type Props = { params: Promise<{ locale: string }> };

// Live backend data — render per request, never at build time.
export const dynamic = "force-dynamic";

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
