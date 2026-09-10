import { getTranslations, setRequestLocale } from "next-intl/server";
import type { Metadata } from "next";
import { getPersons, type PersonRead } from "@/lib/api";
import { PersonDetail, PersonDataError } from "@/components/people/PersonDetail";
import { PersonNotFound } from "@/components/people/PersonNotFound";

type Props = { params: Promise<{ locale: string; personId: string }> };

// Live backend data — render per request, never at build time.
export const dynamic = "force-dynamic";

// Tab title — the section name (the person's own name is only known
// after the list fetch inside the page render; a metadata-time fetch
// would duplicate it for no operational value).
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "app.pages.people" });
  return { title: t("title") };
}

// Person detail. The backend has no single-person endpoint (Phase 3 is
// frozen), so the page reads the existing GET /api/persons list once,
// locates the person by id in memory, and renders it. No new endpoint,
// no ad-hoc fetch, no repeated requests per render.
export default async function Page({ params }: Props) {
  const { locale, personId } = await params;
  setRequestLocale(locale);

  let people: PersonRead[];
  try {
    people = await getPersons();
  } catch {
    // List fetch failure — localized error state, no stack traces.
    return <PersonDataError />;
  }

  const person = people.find((p) => p.id === personId);
  if (!person) {
    return <PersonNotFound />;
  }

  return <PersonDetail person={person} />;
}
