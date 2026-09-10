"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import type { EventRead } from "@/lib/api";

// One event block inside a day column. Position is absolute (top from
// the grid's minute mapping; side offset from the overlap lane). The
// block is a Link to the Event Detail page. The accessible name
// carries the full context (title, time, status, and the
// outside-visible-hours marker when clamped) so the visual position
// is never the only information channel.
export function CalendarEvent({
  event,
  top,
  lane,
  lanes,
  outside,
  timeLabel,
  statusLabel,
  outsideLabel,
}: {
  event: EventRead;
  top: number;
  lane: number;
  lanes: number;
  outside: "before" | "after" | null;
  timeLabel: string;
  statusLabel: string;
  outsideLabel: string;
}) {
  const t = useTranslations("calendar");

  const widthPercent = 100 / lanes;
  const accessibleName = [
    `${t("eventLink")}: ${event.title}`,
    timeLabel,
    statusLabel,
    outside ? outsideLabel : null,
  ]
    .filter(Boolean)
    .join(" — ");

  return (
    <Link
      href={`/events/${event.id}`}
      aria-label={accessibleName}
      // text-foreground (not text-primary) for WCAG AA contrast on the
      // primary/10 tint in BOTH themes — primary text measured 4.49:1
      // (light) and 3.50:1 (dark) against the composited background.
      // The primary border/tint/hover keep the interactive affordance.
      className="absolute z-10 flex flex-col gap-0.5 overflow-hidden rounded-md border border-primary/40 bg-primary/10 p-1.5 text-start text-xs text-foreground hover:bg-primary/20"
      style={{
        top,
        height: 48,
        insetInlineStart: `calc(${lane * widthPercent}% + 2px)`,
        width: `calc(${widthPercent}% - 4px)`,
        ...(outside ? { borderStyle: "dashed" } : {}),
      }}
    >
      <span className="truncate font-medium">{event.title}</span>
      <span className="truncate opacity-80">
        {outside === "before" ? "▲ " : outside === "after" ? "▼ " : ""}
        {timeLabel}
      </span>
      {lanes <= 2 ? (
        <span className="truncate opacity-80">{event.type}</span>
      ) : null}
    </Link>
  );
}
