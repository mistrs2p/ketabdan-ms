import type { Metadata } from "next";
import localFont from "next/font/local";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import type { Locale } from "@/i18n/routing";
import { AuthProvider } from "@/lib/auth";
import { themeInitScript } from "@/theme-init";
import "../globals.css";

// Project fonts, self-hosted as variable woff2 files (no external
// requests at runtime, no CDN dependency). Both are loaded once here
// and exposed as CSS variables; globals.css decides which one leads
// the stack per language (fa → Vazirmatn first, en → Inter first), so
// each locale gets its intended primary face while the other font and
// the system stack stay as fallbacks.
const vazirmatn = localFont({
  src: "../fonts/Vazirmatn-Variable.woff2",
  variable: "--font-vazirmatn",
  display: "swap",
  weight: "100 900",
});

const inter = localFont({
  src: "../fonts/InterVariable.woff2",
  variable: "--font-inter",
  display: "swap",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: {
    default: "Ketabdaneh",
    template: "%s | Ketabdaneh",
  },
  description: "Branch operations management system for a Ketabdaneh branch",
};

// Static rendering: pre-render every locale at build time.
export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
  params,
}: Readonly<{
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}>) {
  const { locale } = await params;
  if (!routing.locales.includes(locale as Locale)) {
    notFound();
  }
  setRequestLocale(locale);

  // fa → RTL, en → LTR. Direction is inherited naturally by all children.
  const direction = locale === "fa" ? "rtl" : "ltr";
  const messages = await getMessages();

  return (
    <html
      lang={locale}
      dir={direction}
      suppressHydrationWarning
      className={`${vazirmatn.variable} ${inter.variable}`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <NextIntlClientProvider messages={messages}>
          {/* Auth session provider (Phase 5.3) — nested inside the intl
              provider so the login UI can translate; every page, client
              or server, renders beneath it. Client component; children
              stay server-rendered where they were before. */}
          <AuthProvider>{children}</AuthProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
