import { getTranslations, setRequestLocale } from "next-intl/server";
import type { Metadata } from "next";
import { EventCreateForm } from "@/components/events/EventCreateForm";

type Props = { params: Promise<{ locale: string }> };

// Live backend contract — render per request, never at build time.
export const dynamic = "force-dynamic";

// Tab title from the existing events.create.title message.
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "events.create" });
  return { title: t("title") };
}

// Create Event. Unlike Person creation, the form needs no server-side
// reference data (event type is free text, TBD-D5), so the page is a
// thin shell around the client form.
export default async function Page({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <EventCreateForm />;
}
