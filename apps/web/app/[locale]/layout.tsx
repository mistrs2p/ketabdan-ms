import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import type { Locale } from "@/i18n/routing";
import { themeInitScript } from "@/theme-init";
import "../globals.css";
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
    <html lang={locale} dir={direction} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <NextIntlClientProvider messages={messages}>
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
