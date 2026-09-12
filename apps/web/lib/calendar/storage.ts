/**
 * Calendar-system preference persistence (browser localStorage).
 *
 * Same pattern as the theme and the auth token: browser APIs are
 * never touched during server rendering (`window` checked first), a
 * missing/invalid value is indistinguishable from "no preference"
 * (the locale default applies), and the value only ever flows through
 * these functions.
 */

import {
  isCalendarSystem,
  type CalendarSystem,
} from "./types";

const STORAGE_KEY = "ketabdaneh.pref.calendar";

/** True when running in a browser (client-side) context. */
function isBrowser(): boolean {
  return typeof window !== "undefined";
}

/** Read the persisted preference; `null` when absent or invalid. */
export function readCalendarSystem(): CalendarSystem | null {
  if (!isBrowser()) return null;
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return isCalendarSystem(value) ? value : null;
  } catch {
    // Storage unavailable (private mode, blocked, …) — no preference.
    return null;
  }
}

/** Persist the preference. Empty values remove it (back to default). */
export function saveCalendarSystem(system: CalendarSystem): void {
  if (!isBrowser()) return;
  try {
    window.localStorage.setItem(STORAGE_KEY, system);
  } catch {
    // Storage unavailable — the in-memory choice still applies for
    // this session; it just won't survive a refresh.
  }
}
