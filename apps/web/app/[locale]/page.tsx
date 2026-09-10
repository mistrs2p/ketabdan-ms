import { redirect } from "@/i18n/routing";
import type { Locale } from "@/i18n/routing";

type Props = { params: Promise<{ locale: string }> };

// The locale root. The former foundation-preview demo page (sample
// card, sample button — rendered outside the app shell) was Phase 4
// scaffolding; the application's home is the Dashboard, so the root
// redirects there. The locale-aware redirect keeps the URL prefix
// (/fa/… or /en/…) intact.
export default async function RootPage({ params }: Props) {
  const { locale } = await params;
  redirect({ href: "/dashboard", locale: locale as Locale });
}
