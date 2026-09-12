"use client";

import { useTranslations } from "next-intl";

// Loading skeleton for the Calendar route — shown by loading.tsx
// during navigation and by the Calendar screen itself while its
// client-side fetch is in flight. Mirrors the weekly grid shape
// (toolbar, day headers, body) rather than a generic paragraph, so
// the loading→loaded transition is calm.
export function CalendarLoading() {
  const t = useTranslations("calendar");

  return (
    <div className="flex w-full flex-col gap-3" role="status" aria-label={t("loading")}>
      <span className="text-sm text-muted-foreground">{t("loading")}</span>
      <div className="h-10 animate-pulse rounded-lg border border-border bg-surface" />
      <div className="grid grid-cols-[4.5rem_repeat(7,minmax(0,1fr))] gap-0 overflow-hidden rounded-lg border border-border bg-surface">
        {Array.from({ length: 8 }, (_, i) => (
          <div key={i} className="h-10 animate-pulse border-s border-border" />
        ))}
      </div>
      <div className="h-96 animate-pulse rounded-lg border border-border bg-surface" />
    </div>
  );
}
