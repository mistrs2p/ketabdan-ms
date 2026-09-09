import { defineRouting } from "next-intl/routing";
import { createNavigation } from "next-intl/navigation";

export const locales = ["fa", "en"] as const;
export type Locale = (typeof locales)[number];

export const routing = defineRouting({
  locales,
  defaultLocale: "fa",
});

export type Pathnames = Record<string, string>;

export const { Link, redirect, usePathname, useRouter, getPathname } =
  createNavigation(routing);
