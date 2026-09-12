"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";

// Empty state for the People list (GET /api/persons → []). The add CTA
// links to the real Create Person flow (/people/new).
export function PeopleEmptyState() {
  const t = useTranslations("people");

  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-border bg-surface p-10 text-center">
      <h2 className="text-lg font-bold">{t("empty.title")}</h2>
      <p className="text-muted-foreground">{t("empty.description")}</p>
      <Link
        href="/people/new"
        className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
      >
        {t("addPerson")}
      </Link>
    </div>
  );
}
