"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/routing";
import { navItems } from "./navigation";

// Mobile navigation: a top bar with a hamburger that toggles a dropdown
// panel of the same nav items. Shown below the `md` breakpoint only.
export function MobileNavigation() {
  const t = useTranslations();
  const tApp = useTranslations("app");
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <div className="md:hidden">
      <button
        type="button"
        aria-expanded={open}
        aria-label={tApp("menuLabel")}
        onClick={() => setOpen((v) => !v)}
        className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface text-foreground"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-5 w-5" aria-hidden="true">
          {open ? (
            <path d="m6 6 12 12M18 6 6 18" />
          ) : (
            <path d="M4 6h16M4 12h16M4 18h16" />
          )}
        </svg>
      </button>

      {open && (
        <nav
          aria-label={tApp("navLabel")}
          className="absolute inset-x-0 top-full z-10 flex flex-col gap-1 border-b border-border bg-surface p-2 shadow-lg"
        >
          {navItems.map((item) => {
            const label = t(item.labelKey);
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                onClick={() => setOpen(false)}
                className={
                  active
                    ? "flex items-center gap-3 rounded-lg bg-primary/10 px-3 py-2 text-sm font-medium text-primary"
                    : "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-foreground hover:bg-primary/5"
                }
              >
                {item.icon}
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>
      )}
    </div>
  );
}
