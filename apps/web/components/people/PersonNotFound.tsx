"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";

// Not-found state for a syntactically valid personId with no matching
// person in GET /api/persons. The raw id is deliberately not shown as
// the primary message — a plain localized "person not found" with a
// way back to the People list.
export function PersonNotFound() {
  const t = useTranslations("people.detail.notFound");
  const tPeople = useTranslations("app.pages.people");

  return (
    <div
      className="flex flex-col items-center gap-3 rounded-lg border border-border bg-surface p-10 text-center"
      role="alert"
    >
      <h2 className="text-lg font-bold">{t("title")}</h2>
      <p className="text-muted-foreground">{t("description")}</p>
      <Link
        href="/people"
        className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
      >
        {t("back", { page: tPeople("title") })}
      </Link>
    </div>
  );
}
