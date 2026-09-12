"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  calendarFormatter,
  useCalendarSystem,
} from "@/lib/calendar";
import { weekStartDowForLocale } from "@/components/calendar/weekMath";
import {
  addMonths,
  buildMonthGrid,
  combineDateAndTime,
  dateOf,
  dayPartsOf,
  isSameDay,
  timeStringOf,
} from "./monthGrid";

/**
 * Datetime picker: a trigger button that opens a popover with a month
 * grid plus a time field, styled entirely from the theme tokens so it
 * follows light/dark and RTL automatically. The month grid renders in
 * the viewer's chosen calendar system (Jalali or Gregorian labels over
 * the same real days); the emitted value is always a plain local Date,
 * which the form serializes to ISO-8601 with the browser offset — the
 * system choice never touches the submitted instant.
 *
 * Interaction model (kept deliberately simple): a day button and a
 * non-empty time together form the value; either alone keeps the value
 * empty so the form's required-check behaves like the old input.
 * Outside pointerdown and Escape close the popover.
 */
export function DateTimePicker({
  id,
  value,
  onChange,
  disabled = false,
  invalid = false,
  describedBy,
}: {
  id: string;
  value: Date | null;
  onChange: (value: Date | null) => void;
  disabled?: boolean;
  invalid?: boolean;
  describedBy?: string;
}) {  const t = useTranslations("foundation.dateTimePicker");
  const locale = useLocale();
  const { system } = useCalendarSystem();

  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const [open, setOpen] = useState(false);
  // The viewed month, held as a real Date (its day is irrelevant) so a
  // calendar-system switch mid-navigation just re-labels the same
  // month instead of invalidating the view.
  const [viewAnchor, setViewAnchor] = useState<Date | null>(null);
  // Selection state is the single source of truth once mounted; the
  // `value` prop only seeds it (this form never reassigns the value
  // from outside).
  const [selectedDate, setSelectedDate] = useState<Date | null>(value);
  const [timeStr, setTimeStr] = useState(value ? timeStringOf(value) : "");

  const weekStartDow = useMemo(() => weekStartDowForLocale(locale), [locale]);

  // The viewed month in the current display system.
  const view = dayPartsOf(
    viewAnchor ?? selectedDate ?? new Date(),
    system,
  );
  const viewMonth = { year: view.year, month: view.month };

  const cells = useMemo(
    () =>
      buildMonthGrid(
        { year: view.year, month: view.month },
        weekStartDow,
        system,
      ),
    [view.year, view.month, weekStartDow, system],
  );

  const monthLabelFormatter = useMemo(
    () => calendarFormatter(locale, system, { month: "long", year: "numeric" }),
    [locale, system],
  );
  const valueFormatter = useMemo(
    () =>
      calendarFormatter(locale, system, {
        dateStyle: "medium",
        timeStyle: "short",
      }),
    [locale, system],
  );
  const fullDateFormatter = useMemo(
    () =>
      calendarFormatter(locale, system, {
        dateStyle: "full",
      }),
    [locale, system],
  );
  const dayNumberFormatter = useMemo(
    () => new Intl.NumberFormat(locale),
    [locale],
  );
  // Weekday header labels: narrow names of one real week, rotated to
  // start at the locale's week-start weekday.
  const weekdayLabels = useMemo(() => {
    const formatter = calendarFormatter(locale, system, {
      weekday: "narrow",
    });
    // 2024-01-07 is a Sunday — a stable anchor for one full week.
    const names = Array.from({ length: 7 }, (_, i) =>
      formatter.format(new Date(2024, 0, 7 + i)),
    );
    return Array.from(
      { length: 7 },
      (_, i) => names[(weekStartDow + i) % 7],
    );
  }, [locale, system, weekStartDow]);

  const monthLabel = monthLabelFormatter.format(
    dateOf(viewMonth, 1, system),
  );

  const today = new Date();

  function emit(date: Date | null, time: string) {
    const combined =
      date !== null ? combineDateAndTime(date, time) : null;
    onChange(combined);
  }

  function handleDayClick(cellDate: Date) {
    setSelectedDate(cellDate);
    setViewAnchor(cellDate);
    emit(cellDate, timeStr);
  }

  function handleTimeChange(next: string) {
    setTimeStr(next);
    emit(selectedDate, next);
  }

  function goToToday() {
    const now = new Date();
    setViewAnchor(now);
  }

  // Close on outside pointerdown and on Escape (focus returns to the
  // trigger). Registered only while open.
  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: PointerEvent) {
      if (
        rootRef.current !== null &&
        !rootRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={triggerRef}
        id={id}
        type="button"
        disabled={disabled}
        // aria-invalid is not valid on a button; the invalid state is
        // carried by the red border plus the error message linked via
        // describedBy (role="alert" announces it).
        aria-describedby={describedBy}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className={`flex w-full items-center justify-between gap-2 rounded-lg border bg-background px-3 py-2 text-start text-sm ${
          invalid ? "border-primary" : "border-border"
        }`}
      >
        <span className={value === null ? "text-muted-foreground" : ""}>
          {value !== null
            ? valueFormatter.format(value)
            : t("placeholder")}
        </span>
        {/* Calendar icon — decorative; the label text carries meaning. */}
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="h-4 w-4 shrink-0 text-muted-foreground"
          aria-hidden="true"
        >
          <rect x="3" y="5" width="18" height="16" rx="2" />
          <path d="M8 3v4M16 3v4M3 10h18" />
        </svg>
      </button>

      {open ? (
        <div
          role="dialog"
          aria-label={t("placeholder")}
          className="absolute inset-s-0 z-30 mt-2 w-80 rounded-xl border border-border bg-surface p-3 shadow-lg"
        >
          {/* Month navigation */}
          <div className="flex items-center gap-1">
            <button
              type="button"
              aria-label={t("previousMonth")}
              onClick={() =>
                setViewAnchor(dateOf(addMonths(viewMonth, -1), 1, system))
              }
              className="rounded-lg p-1.5 text-foreground hover:bg-primary/5"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className="h-4 w-4 rtl:rotate-180"
                aria-hidden="true"
              >
                <path d="m15 18-6-6 6-6" />
              </svg>
            </button>
            <p
              className="flex-1 text-center text-sm font-semibold"
              aria-live="polite"
            >
              {monthLabel}
            </p>
            <button
              type="button"
              aria-label={t("nextMonth")}
              onClick={() =>
                setViewAnchor(dateOf(addMonths(viewMonth, 1), 1, system))
              }
              className="rounded-lg p-1.5 text-foreground hover:bg-primary/5"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className="h-4 w-4 rtl:rotate-180"
                aria-hidden="true"
              >
                <path d="m9 18 6-6-6-6" />
              </svg>
            </button>
          </div>

          {/* Weekday header */}
          <div className="mt-2 grid grid-cols-7">
            {weekdayLabels.map((label, i) => (
              <div
                key={i}
                className="py-1 text-center text-xs font-medium text-muted-foreground"
              >
                {label}
              </div>
            ))}
          </div>

          {/* Day grid */}
          <div className="grid grid-cols-7">
            {cells.map((cell) => {
              const selected =
                selectedDate !== null && isSameDay(cell.date, selectedDate);
              const isToday = isSameDay(cell.date, today);
              return (
                <button
                  key={cell.date.toISOString()}
                  type="button"
                  aria-pressed={selected}
                  aria-label={fullDateFormatter.format(cell.date)}
                  onClick={() => handleDayClick(cell.date)}
                  className={`mx-auto my-0.5 flex h-8 w-8 items-center justify-center rounded-full text-sm transition-colors ${
                    selected
                      ? "bg-primary font-semibold text-primary-foreground"
                      : cell.inMonth
                        ? "text-foreground hover:bg-primary/10"
                        : "text-muted-foreground/50 hover:bg-primary/10"
                  } ${
                    isToday && !selected
                      ? "ring-1 ring-primary ring-inset"
                      : ""
                  }`}
                >
                  {dayNumberFormatter.format(cell.day)}
                </button>
              );
            })}
          </div>

          {/* Footer: today shortcut + time */}
          <div className="mt-3 flex items-center justify-between gap-2 border-t border-border pt-3">
            <button
              type="button"
              onClick={goToToday}
              className="rounded-lg px-2.5 py-1.5 text-xs font-medium text-foreground hover:bg-primary/5"
            >
              {t("today")}
            </button>
            <div className="flex items-center gap-2">
              <label
                htmlFor={`${id}-time`}
                className="text-xs font-medium text-muted-foreground"
              >
                {t("time")}
              </label>
              <input
                id={`${id}-time`}
                type="time"
                value={timeStr}
                onChange={(e) => handleTimeChange(e.target.value)}
                className="rounded-lg border border-border bg-background px-2 py-1 text-sm"
              />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
