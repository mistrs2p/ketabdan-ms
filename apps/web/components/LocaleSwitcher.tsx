"use client";

import { useLocale, useTranslations } from "next-intl";
import { usePathname, useRouter } from "@/i18n/routing";
import { routing } from "@/i18n/routing";
import type { Locale } from "@/i18n/routing";

const LOCALE_LABELS: Record<Locale, string> = {
  fa: "فارسی",
  en: "English",
};

export function LocaleSwitcher() {
  const t = useTranslations("foundation");
  const locale = useLocale() as Locale;
  const pathname = usePathname();
  const router = useRouter();

  function switchTo(next: Locale) {
    // Full navigation: next-intl's router updates the URL prefix, and the
    // server layout re-renders <html lang dir> for the new locale.
    router.replace(pathname, { locale: next });
  }

  return (
    <div
      className="flex items-center gap-1 rounded-lg border border-border bg-surface p-1"
      aria-label={t("language")}
    >
      {routing.locales.map((option) => (
        <button
          key={option}
          type="button"
          onClick={() => switchTo(option)}
          disabled={option === locale}
          className={
            option === locale
              ? "rounded-md bg-primary px-3 py-1 text-sm font-medium text-primary-foreground"
              : "rounded-md px-3 py-1 text-sm font-medium text-foreground"
          }
        >
          {LOCALE_LABELS[option]}
        </button>
      ))}
    </div>
  );
}
