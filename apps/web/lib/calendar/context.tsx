"use client";

/**
 * Calendar-system preference provider.
 *
 * Mirrors the auth/theme patterns: server render and the first client
 * render both use the locale default (deterministic HTML, no hydration
 * mismatch); after mount the persisted preference — if any — applies.
 * A change is written to storage and broadcast to every consumer, so
 * all date labels across the app switch together.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useLocale } from "next-intl";
import { readCalendarSystem, saveCalendarSystem } from "./storage";
import {
  defaultCalendarSystemForLocale,
  type CalendarSystem,
} from "./types";

interface CalendarContextValue {
  /** The effective system (persisted choice, else the locale default). */
  system: CalendarSystem;
  /** Switch the system and persist the choice. */
  setSystem: (system: CalendarSystem) => void;
  /** True once the persisted preference (if any) has been applied. */
  ready: boolean;
}

const CalendarContext = createContext<CalendarContextValue | null>(null);

export function CalendarProvider({ children }: { children: ReactNode }) {
  const locale = useLocale();
  // null = not yet decided: server + first client render fall back to
  // the locale default below, keeping both renders identical.
  const [system, setSystemState] = useState<CalendarSystem | null>(null);

  useEffect(() => {
    const persisted = readCalendarSystem();
    if (persisted !== null) {
      setSystemState(persisted);
    }
  }, []);

  const setSystem = useCallback((next: CalendarSystem) => {
    setSystemState(next);
    saveCalendarSystem(next);
  }, []);

  const value: CalendarContextValue = {
    system: system ?? defaultCalendarSystemForLocale(locale),
    setSystem,
    ready: system !== null,
  };

  return (
    <CalendarContext.Provider value={value}>
      {children}
    </CalendarContext.Provider>
  );
}

/** Access the viewer's calendar-system preference. */
export function useCalendarSystem(): CalendarContextValue {
  const value = useContext(CalendarContext);
  if (value === null) {
    throw new Error(
      "useCalendarSystem must be used within a CalendarProvider",
    );
  }
  return value;
}
