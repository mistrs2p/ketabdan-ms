"use client";

import { useTranslations } from "next-intl";

// Loading skeleton for the People routes. Shown by loading.tsx during
// navigation and by the People screen itself while its client-side
// fetch is in flight. Mirrors the table layout so the transition is
// calm; text makes the state explicit without color cues.
export function PeopleLoading() {
  const t = useTranslations("people");

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
