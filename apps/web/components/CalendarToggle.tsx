"use client";

import { useTranslations } from "next-intl";
import { useCalendarSystem } from "@/lib/calendar";
import type { CalendarSystem } from "@/lib/calendar";

/**
 * Segmented calendar-system switch (Jalali vs Gregorian display),
 * next to the theme and locale controls. The active segment carries
 * both color and aria-pressed, so the current state is never conveyed
 * by color alone. Until the persisted preference loads, the segments
 * still render with the locale default — no layout shift on switch.
 */
export function CalendarToggle() {
  const t = useTranslations("foundation.calendarToggle");
  const { system, setSystem } = useCalendarSystem();

  const segments: { value: CalendarSystem; label: string }[] = [
    { value: "persian", label: t("persian") },
    { value: "gregory", label: t("gregorian") },
  ];

  return (
    <div
      role="group"
      aria-label={t("label")}
      className="flex items-center overflow-hidden rounded-lg border border-border bg-surface"
    >
      {segments.map(({ value, label }) => {
        const active = system === value;
        return (
          <button
            key={value}
            type="button"
            aria-pressed={active}
            onClick={() => setSystem(value)}
            className={`px-2.5 py-1.5 text-sm font-medium transition-colors ${
              active
                ? "bg-primary text-primary-foreground"
                : "text-foreground hover:bg-primary/5"
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
