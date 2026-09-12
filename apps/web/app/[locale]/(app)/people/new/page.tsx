import { getTranslations, setRequestLocale } from "next-intl/server";
import type { Metadata } from "next";
import { PersonCreateLoader } from "@/components/people/PersonCreateLoader";

type Props = { params: Promise<{ locale: string }> };

// The shell renders per request; the role reference data is fetched
// client-side (see PersonCreateLoader) because the access token lives
// in browser localStorage.
export const dynamic = "force-dynamic";

// Tab title from the existing people.create.title message.
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "people.create" });
  return { title: t("title") };
}

// Create Person. The page is a thin server shell (metadata + locale);
// PersonCreateLoader fetches the role reference data (GET /api/roles)
// in the browser, where the auth token lives, and hands it to the
// interactive form.
export default async function Page({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <PersonCreateLoader />;
}
