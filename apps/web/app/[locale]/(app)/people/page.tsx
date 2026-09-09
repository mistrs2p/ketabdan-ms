import { setRequestLocale } from "next-intl/server";
import { PeoplePage } from "@/components/people/PeoplePage";

type Props = { params: Promise<{ locale: string }> };

// Live backend data — render per request, never at build time.
export const dynamic = "force-dynamic";

// People list — the first real domain screen (Phase 4). The shell,
// navigation, locale, direction, and theme all come from the existing
// app layout; this page only renders the people content.
export default async function Page({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <PeoplePage />;
}
