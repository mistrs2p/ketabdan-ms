import { getTranslations, setRequestLocale } from "next-intl/server";
import type { Metadata } from "next";
import { PersonDetailLoader } from "@/components/people/PersonDetailLoader";

type Props = { params: Promise<{ locale: string; personId: string }> };

// The shell renders per request; the business data itself is fetched
// client-side (see PersonDetailLoader) because the access token lives
// in browser localStorage.
export const dynamic = "force-dynamic";

// Tab title — the section name (the person's own name is only known
// after the client-side fetch; a metadata-time fetch would duplicate
// it for no operational value).
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "app.pages.people" });
  return { title: t("title") };
}

// Person detail. The page is a thin server shell (metadata + locale);
// PersonDetailLoader fetches the persons list in the browser, where
// the auth token lives, and locates the person by id in memory (no
// single-person endpoint exists — Phase 3 is frozen).
export default async function Page({ params }: Props) {
  const { locale, personId } = await params;
  setRequestLocale(locale);

  return <PersonDetailLoader personId={personId} />;
}
