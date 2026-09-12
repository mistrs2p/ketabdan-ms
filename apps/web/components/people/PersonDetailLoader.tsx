"use client";

import { getPersons } from "@/lib/api";
import { useApiData } from "@/hooks/useApiData";
import { PersonDetail, PersonDataError } from "./PersonDetail";
import { PersonNotFound } from "./PersonNotFound";
import { PeopleLoading } from "./PeopleLoading";

// Client-side data loading for the person detail screen. A Client
// Component because the access token lives in browser localStorage,
// which the server page cannot read — the fetch must run in the
// browser, where the AuthGate has already confirmed the session.
//
// The backend has no single-person endpoint (Phase 3 is frozen), so
// this loads the existing GET /api/persons list once, locates the
// person by id in memory, and renders it. No new endpoint, no ad-hoc
// fetch, no repeated requests per render. The person is looked up
// from the current personId on every render, so a URL change within
// the screen resolves without a refetch.
export function PersonDetailLoader({ personId }: { personId: string }) {
  const state = useApiData(getPersons);

  if (state.status === "loading") {
    return <PeopleLoading />;
  }
  if (state.status === "error") {
    // List fetch failure — localized error state, no stack traces.
    return <PersonDataError />;
  }

  const person = state.data.find((p) => p.id === personId);
  if (!person) {
    return <PersonNotFound />;
  }

  return <PersonDetail person={person} />;
}
