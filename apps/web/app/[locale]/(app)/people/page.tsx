import { getTranslations, setRequestLocale } from "next-intl/server";
import type { Metadata } from "next";
import { PeoplePage } from "@/components/people/PeoplePage";

type Props = { params: Promise<{ locale: string }> };

// The shell renders per request; the business data itself is fetched
// client-side (see PeoplePage) because the access token lives in
// browser localStorage.
export const dynamic = "force-dynamic";

// Tab title from the existing app.pages.people.title message.
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "app.pages.people" });
  return { title: t("title") };
}

// People list — the first real domain screen (Phase 4). The shell,
// navigation, locale, direction, and theme all come from the existing
// app layout; this page only renders the people content.
export default async function Page({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <PeoplePage />;
}
