import { getTranslations } from "next-intl/server";
import { getPersons, ApiError, type PersonRead } from "@/lib/api";
import { PeopleTable } from "./PeopleTable";
import { PeopleEmptyState } from "./PeopleEmptyState";
import { PeopleErrorState } from "./PeopleErrorState";

// The People list screen. A Server Component: it calls the typed API
// layer (getPersons) directly — no fetch boilerplate, no client data
// framework. Backend ordering (name, then id) is preserved; the UI
// never re-sorts.
//
// States: loading via the sibling loading.tsx (streaming), error /
// empty / data handled here. The "Add person" button is visual-only —
// creation is a later task and must not fake success.
export async function PeoplePage() {
  const t = await getTranslations("people");
  const tTitle = await getTranslations("app.pages.people");

  let people: PersonRead[] = [];
  let error: ApiError | undefined;
  try {
    people = await getPersons();
  } catch (e) {
    if (e instanceof ApiError) {
      error = e;
    } else {
      // Unexpected client-layer error — present as a generic server
      // failure rather than crashing the page.
      error = new ApiError("server", String(e));
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold">{tTitle("title")}</h1>
          <p className="text-muted-foreground">{t("description")}</p>
        </div>
        <button
          type="button"
          disabled
          title={t("addPersonDisabledHint")}
          className="cursor-not-allowed rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground opacity-50"
        >
          {t("addPerson")}
        </button>
      </header>

      {error ? <PeopleErrorState error={error} /> : null}
      {!error && people.length === 0 ? <PeopleEmptyState /> : null}
      {!error && people.length > 0 ? <PeopleTable people={people} /> : null}
    </div>
  );
}
