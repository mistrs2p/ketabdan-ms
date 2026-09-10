// Date-only math for the weekly calendar. All dates here are
// UTC-anchored midnights (Date.UTC) — pure calendar arithmetic with no
// timezone drift, deterministic on server and client alike. When such
// a date is FORMATTED, it is always formatted with timeZone: "UTC" so
// the displayed day matches the arithmetic. Real event instants are
// never routed through these helpers.

const DAY_MS = 86_400_000;

export interface DateParts {
  year: number;
  month: number; // 1-12
  day: number;
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

/** The server's local calendar date as "YYYY-MM-DD" (base for "today"). */
export function todayIsoDate(): string {
  const now = new Date();
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** Parse a "YYYY-MM-DD" string; null when malformed. */
export function parseIsoDate(iso: string): DateParts | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return null;
  return { year: Number(match[1]), month: Number(match[2]), day: Number(match[3]) };
}

/** UTC-anchored midnight Date for date-only parts. */
export function toUtcDate(parts: DateParts): Date {
  return new Date(Date.UTC(parts.year, parts.month - 1, parts.day));
}

/** Date-only parts of a UTC-anchored Date. */
export function partsOf(date: Date): DateParts {
  return {
    year: date.getUTCFullYear(),
    month: date.getUTCMonth() + 1,
    day: date.getUTCDate(),
  };
}

/** ISO "YYYY-MM-DD" of a UTC-anchored Date. */
export function isoOf(date: Date): string {
  const p = partsOf(date);
  return `${p.year}-${pad(p.month)}-${pad(p.day)}`;
}

/** Shift a UTC-anchored date by n days. */
export function addDays(date: Date, n: number): Date {
  return new Date(date.getTime() + n * DAY_MS);
}

/**
 * Week-start weekday (0=Sun … 6=Sat) for a locale, from the runtime's
 * Intl week data — a *presentation* choice, not a business rule: fa
 * conventionally starts on Saturday, en typically on Sunday/Monday
 * depending on region. The underlying event data stays Gregorian/ISO
 * (no Jalali conversion). Fallback: Saturday for fa, Sunday otherwise.
 */
export function weekStartDowForLocale(locale: string): number {
  try {
    const intlLocale = new Intl.Locale(locale) as Intl.Locale & {
      weekInfo?: { firstDay?: number };
    };
    const firstDay = intlLocale.weekInfo?.firstDay;
    // weekInfo.firstDay: 1=Mon … 7=Sun → convert to 0=Sun convention
    if (typeof firstDay === "number" && firstDay >= 1 && firstDay <= 7) {
      return firstDay % 7;
    }
  } catch {
    // fall through to the static fallback
  }
  return locale.toLowerCase().startsWith("fa") ? 6 : 0;
}

/** Start of the week containing `date`, given the week-start weekday. */
export function startOfWeek(date: Date, weekStartDow: number): Date {
  const dow = date.getUTCDay();
  const diff = (dow - weekStartDow + 7) % 7;
  return addDays(date, -diff);
}
