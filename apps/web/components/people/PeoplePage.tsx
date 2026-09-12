"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import { getPersons } from "@/lib/api";
import { useApiData } from "@/hooks/useApiData";
import { PeopleTable } from "./PeopleTable";
import { PeopleEmptyState } from "./PeopleEmptyState";
import { PeopleErrorState } from "./PeopleErrorState";
import { PeopleLoading } from "./PeopleLoading";

// The People list screen. A Client Component: the access token lives
// in browser localStorage, which a server component cannot read — a
// server-side fetch would go out unauthenticated and fail 401. The
// list is therefore fetched on mount, after the AuthGate has
// confirmed the session (see hooks/useApiData).
//
// The typed API layer (getPersons) is called directly — no client
// data framework. Backend ordering (name, then id) is preserved; the
// UI never re-sorts. States: loading / error / empty / data handled
// here. The "Add person" button navigates to the Create Person flow
// (/people/new) via the localized routing helpers.
export function PeoplePage() {
  const t = useTranslations("people");
  const tTitle = useTranslations("app.pages.people");
  const state = useApiData(getPersons);

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold">{tTitle("title")}</h1>
          <p className="text-muted-foreground">{t("description")}</p>
        </div>
        <Link
          href="/people/new"
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          {t("addPerson")}
        </Link>
      </header>

      {state.status === "loading" ? <PeopleLoading /> : null}
      {state.status === "error" ? <PeopleErrorState error={state.error} /> : null}
      {state.status === "success" && state.data.length === 0 ? (
        <PeopleEmptyState />
      ) : null}
      {state.status === "success" && state.data.length > 0 ? (
        <PeopleTable people={state.data} />
      ) : null}
    </div>
  );
}
