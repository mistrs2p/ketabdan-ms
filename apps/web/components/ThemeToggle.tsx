"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

const STORAGE_KEY = "ketabdaneh-theme";
type Theme = "light" | "dark";

function getInitialTheme(): Theme | null {
  return null; // server and first client render stay theme-agnostic
}

export function ThemeToggle() {
  const t = useTranslations("foundation.themeToggle");
  const [theme, setTheme] = useState<Theme | null>(getInitialTheme());

  // Read the theme the pre-paint script already applied to <html>.
  useEffect(() => {
    const current = document.documentElement.dataset.theme;
    setTheme(current === "dark" ? "dark" : "light");
  }, []);

  // Persist and apply on change.
  useEffect(() => {
    if (theme === null) return;
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // Storage unavailable (private mode, etc.) — theme still applies.
    }
  }, [theme]);

  const isDark = theme === "dark";

  return (
    <button
      type="button"
      aria-pressed={isDark}
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium text-foreground"
    >
      {isDark ? t("dark") : t("light")}
    </button>
  );
}
