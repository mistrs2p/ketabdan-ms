"use client";

import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/routing";
import { navItems } from "./navigation";

// Desktop/tablet sidebar. Hidden below the `md` breakpoint, where
// MobileNavigation takes over. Logical borders/padding keep RTL/LTR natural.
export function Sidebar() {
  const t = useTranslations();
  const tApp = useTranslations("app");
  const pathname = usePathname();

  return (
    <aside className="hidden min-h-dvh w-64 shrink-0 flex-col border-e border-border bg-surface md:flex">
      <div className="flex items-center gap-2 px-4 py-4">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
          ک
        </span>
        <span className="text-lg font-bold">{tApp("name")}</span>
      </div>
      <nav className="flex flex-1 flex-col gap-1 px-2 py-2" aria-label={tApp("navLabel")}>
        {navItems.map((item) => {
          const label = t(item.labelKey);
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
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
    </aside>
  );
}
