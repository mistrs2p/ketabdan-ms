import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/routing";
import type { PersonRead } from "@/lib/api";

// Person detail screen. A Server Component: everything here is read-only
// display of the PersonRead contract. The Edit control is deliberately
// disabled — no backend update contract exists (Phase 3 frozen), and
// nothing may fake persistence. Status is text (not color-only); role
// names come from backend reference data; phone null shows the localized
// "not provided" value.
export async function PersonDetail({ person }: { person: PersonRead }) {
  const t = await getTranslations("people.detail");
  const tPeople = await getTranslations("app.pages.people");

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold">{person.name}</h1>
          <p className="text-muted-foreground">{t("description")}</p>
        </div>
        {/* No backend update contract exists yet — disabled, not faked. */}
        <button
          type="button"
          disabled
          title={t("editDisabledHint")}
          className="cursor-not-allowed rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground opacity-50"
        >
          {t("edit")}
        </button>
      </header>

      <dl className="flex flex-col divide-y divide-border rounded-lg border border-border bg-surface">
        <div className="flex flex-col gap-1 p-4 sm:flex-row sm:items-baseline sm:gap-4">
          <dt className="w-40 shrink-0 text-sm font-medium text-muted-foreground">
            {t("name")}
          </dt>
          <dd className="text-sm">{person.name}</dd>
        </div>
        <div className="flex flex-col gap-1 p-4 sm:flex-row sm:items-baseline sm:gap-4">
          <dt className="w-40 shrink-0 text-sm font-medium text-muted-foreground">
            {t("phone")}
          </dt>
          <dd className="text-sm">{person.phone ?? t("phoneUnavailable")}</dd>
        </div>
        <div className="flex flex-col gap-1 p-4 sm:flex-row sm:items-baseline sm:gap-4">
          <dt className="w-40 shrink-0 text-sm font-medium text-muted-foreground">
            {t("status")}
          </dt>
          <dd className="text-sm">
            <span
              className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-xs ${
                person.active
                  ? "bg-primary/10 text-primary"
                  : "bg-muted-foreground/10 text-muted-foreground"
              }`}
            >
              {/* Status is carried by the text label; the dot only reinforces it. */}
              <span
                aria-hidden="true"
                className={`h-1.5 w-1.5 rounded-full ${
                  person.active ? "bg-primary" : "bg-muted-foreground"
                }`}
              />
              {person.active ? t("statusActive") : t("statusInactive")}
            </span>
          </dd>
        </div>
        <div className="flex flex-col gap-1 p-4 sm:flex-row sm:gap-4">
          <dt className="w-40 shrink-0 text-sm font-medium text-muted-foreground">
            {t("roles")}
          </dt>
          <dd className="text-sm">
            {person.roles.length === 0 ? (
              <span className="text-muted-foreground">{t("noRoles")}</span>
            ) : (
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
            )}
          </dd>
        </div>
      </dl>

      <div>
        <Link
          href="/people"
          className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-primary/5"
        >
          {t("back", { page: tPeople("title") })}
        </Link>
      </div>
    </div>
  );
}

// List fetch failure while loading the person (GET /api/persons failed).
// Network vs server wording comes from the ApiError kind at the call
// site; this component renders the generic data-error state.
export async function PersonDataError() {
  const t = await getTranslations("people.detail.error");

  return (
    <div
      className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-6"
      role="alert"
    >
      <h2 className="text-lg font-bold">{t("title")}</h2>
      <p className="text-muted-foreground">{t("server")}</p>
      <Link
        href="/people"
        className="text-sm font-medium text-primary hover:underline"
      >
        {t("back")}
      </Link>
    </div>
  );
}
