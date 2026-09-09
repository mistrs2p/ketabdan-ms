import { setRequestLocale } from "next-intl/server";
import { EventCreateForm } from "@/components/events/EventCreateForm";

type Props = { params: Promise<{ locale: string }> };

// Live backend contract — render per request, never at build time.
export const dynamic = "force-dynamic";

// Create Event. Unlike Person creation, the form needs no server-side
// reference data (event type is free text, TBD-D5), so the page is a
// thin shell around the client form.
export default async function Page({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <EventCreateForm />;
}
