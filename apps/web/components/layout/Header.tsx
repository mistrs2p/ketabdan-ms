"use client";

import { useTranslations } from "next-intl";
import { CalendarToggle } from "@/components/CalendarToggle";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { ThemeToggle } from "@/components/ThemeToggle";
import { MobileNavigation } from "./MobileNavigation";
import { UserMenu } from "./UserMenu";

// Topbar: mobile nav on the start side, page context in the middle,
// user identity + sign-out and theme/language controls on the end side.
// Logical utilities (justify-between, gap) mirror automatically in
// RTL/LTR.
export function Header() {
  const t = useTranslations("app.header");

  return (
    <header className="sticky top-0 z-10 flex h-14 items-center justify-between gap-3 border-b border-border bg-surface px-4">
      <div className="flex items-center gap-2">
        <MobileNavigation />
      </div>
      <div className="min-w-0 flex-1 text-sm text-muted-foreground">{t("context")}</div>
      <div className="flex items-center gap-2">
        <UserMenu />
        <ThemeToggle />
        <CalendarToggle />
        <LocaleSwitcher />
      </div>
    </header>
  );
}
