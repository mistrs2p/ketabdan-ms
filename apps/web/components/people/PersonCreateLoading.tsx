"use client";

import { useTranslations } from "next-intl";

// Loading UI for the Create Person route — shown by loading.tsx during
// navigation and by the Create Person screen itself while its
// client-side role reference fetch (GET /api/roles) is in flight.
export function PersonCreateLoading() {
  const t = useTranslations("people.create");

  return (
    <div
      className="flex flex-col gap-3"
      role="status"
      aria-label={t("loading")}
    >
      <span className="text-sm text-muted-foreground">{t("loading")}</span>
      {Array.from({ length: 4 }, (_, i) => (
        <div
          key={i}
          className="h-14 animate-pulse rounded-lg border border-border bg-surface"
        />
      ))}
    </div>
  );
}
