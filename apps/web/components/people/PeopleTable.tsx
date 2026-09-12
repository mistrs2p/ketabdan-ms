"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import type { PersonRead } from "@/lib/api";

// People table. Desktop (≥ md): a semantic table. Below md: the same
// data as stacked cards — a wide table squeezed onto a phone would
// break. Role labels come from the role row's `name` (backend
// reference data) — never hard-coded. Status is shown as text
// (not color-only). The View action links to the person detail page
// via the localized routing helper.
export function PeopleTable({ people }: { people: PersonRead[] }) {
  const t = useTranslations("people");

  return (
    <>
      {/* Desktop table */}
      <table className="hidden w-full border-collapse text-start text-sm md:table">
        <caption className="sr-only">{t("table.caption")}</caption>
        <thead>
          <tr className="border-b border-border text-start">
            <th scope="col" className="px-4 py-3 text-start font-medium">
              {t("table.name")}
            </th>
            <th scope="col" className="px-4 py-3 text-start font-medium">
              {t("table.phone")}
            </th>
            <th scope="col" className="px-4 py-3 text-start font-medium">
              {t("table.roles")}
            </th>
            <th scope="col" className="px-4 py-3 text-start font-medium">
              {t("table.status")}
            </th>
            <th scope="col" className="px-4 py-3 text-start font-medium">
              {t("table.actions")}
            </th>
          </tr>
        </thead>
        <tbody>
          {people.map((person) => (
            <tr key={person.id} className="border-b border-border last:border-b-0">
              <td className="px-4 py-3 font-medium">{person.name}</td>
              <td className="px-4 py-3 text-muted-foreground">
                {person.phone ?? t("phoneUnavailable")}
              </td>
              <td className="px-4 py-3">
                <RolesCell person={person} noRolesLabel={t("noRoles")} />
              </td>
              <td className="px-4 py-3">
                <StatusCell
                  active={person.active}
                  activeLabel={t("status.active")}
                  inactiveLabel={t("status.inactive")}
                />
              </td>
              <td className="px-4 py-3">
                <ViewAction
                  personId={person.id}
                  personName={person.name}
                  label={t("viewAction")}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Mobile cards */}
      <ul className="flex flex-col gap-3 md:hidden">
        {people.map((person) => (
          <li
            key={person.id}
            className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-4"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">{person.name}</span>
              <StatusCell
                active={person.active}
                activeLabel={t("status.active")}
                inactiveLabel={t("status.inactive")}
              />
            </div>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
              <dt className="text-muted-foreground">{t("table.phone")}</dt>
              <dd>{person.phone ?? t("phoneUnavailable")}</dd>
              <dt className="text-muted-foreground">{t("table.roles")}</dt>
              <dd className="flex flex-wrap gap-1">
                {person.roles.length === 0 ? (
                  t("noRoles")
                ) : (
                  person.roles.map((role) => (
                    <span
                      key={role.id}
                      className="rounded bg-primary/10 px-2 py-0.5 text-xs text-primary"
                    >
                      {role.name}
                    </span>
                  ))
                )}
              </dd>
            </dl>
            <div>
              <ViewAction
                personId={person.id}
                personName={person.name}
                label={t("viewAction")}
              />
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}

function RolesCell({
  person,
  noRolesLabel,
}: {
  person: PersonRead;
  noRolesLabel: string;
}) {
  if (person.roles.length === 0) {
    return <span className="text-muted-foreground">{noRolesLabel}</span>;
  }
  return (
    <span className="flex flex-wrap gap-1">
      {person.roles.map((role) => (
        <span
          key={role.id}
          className="rounded bg-primary/10 px-2 py-0.5 text-xs text-primary"
        >
          {role.name}
        </span>
      ))}
    </span>
  );
}

function StatusCell({
  active,
  activeLabel,
  inactiveLabel,
}: {
  active: boolean;
  activeLabel: string;
  inactiveLabel: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-xs ${
        active
          ? "bg-primary/10 text-primary"
          : "bg-muted-foreground/10 text-muted-foreground"
      }`}
    >
      {/* Status is carried by the text label; the dot only reinforces it. */}
      <span
        aria-hidden="true"
        className={`h-1.5 w-1.5 rounded-full ${
          active ? "bg-primary" : "bg-muted-foreground"
        }`}
      />
      {active ? activeLabel : inactiveLabel}
    </span>
  );
}

function ViewAction({
  personId,
  personName,
  label,
}: {
  personId: string;
  personName: string;
  label: string;
}) {
  return (
    <Link
      href={`/people/${personId}`}
      aria-label={`${label}: ${personName}`}
      className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-primary/5"
    >
      {label}
    </Link>
  );
}
