// Single source of truth for the application's primary navigation,
// consumed by both Sidebar and MobileNavigation.

export type NavItem = {
  href: string;
  labelKey: string;
  icon: React.ReactNode;
};

// Placeholder inline icons — no icon library dependency. When a real icon
// set is chosen for the design system, only this file's icons change.
const iconClass = "h-5 w-5 shrink-0";

const icons = {
  dashboard: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={iconClass} aria-hidden="true">
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </svg>
  ),
  calendar: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={iconClass} aria-hidden="true">
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M8 3v4M16 3v4M3 10h18" />
    </svg>
  ),
  events: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={iconClass} aria-hidden="true">
      <path d="M8 7V3m8 4V3M3 9h18M5 5h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z" />
      <path d="m9 15 2 2 4-4" />
    </svg>
  ),
  tasks: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={iconClass} aria-hidden="true">
      <path d="M4 6h10M4 12h10M4 18h10" />
      <path d="m16 5 2 2 3-3M16 11l2 2 3-3M16 17l2 2 3-3" />
    </svg>
  ),
  people: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={iconClass} aria-hidden="true">
      <circle cx="9" cy="8" r="3.5" />
      <path d="M2.5 20a6.5 6.5 0 0 1 13 0" />
      <path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M21.5 20a6.5 6.5 0 0 0-4.5-6.2" />
    </svg>
  ),
};

export const navItems: NavItem[] = [
  { href: "/dashboard", labelKey: "nav.dashboard", icon: icons.dashboard },
  { href: "/calendar", labelKey: "nav.calendar", icon: icons.calendar },
  { href: "/events", labelKey: "nav.events", icon: icons.events },
  { href: "/tasks", labelKey: "nav.tasks", icon: icons.tasks },
  { href: "/people", labelKey: "nav.people", icon: icons.people },
];
