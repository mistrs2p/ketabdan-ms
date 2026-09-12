"use client";

import { getRoles } from "@/lib/api";
import { useApiData } from "@/hooks/useApiData";
import { PersonCreateForm } from "./PersonCreateForm";
import { PersonCreateLoading } from "./PersonCreateLoading";

// Client-side data loading for the Create Person screen. A Client
// Component because the access token lives in browser localStorage,
// which the server page cannot read — the role reference fetch (GET
// /api/roles) must run in the browser, where the AuthGate has already
// confirmed the session.
//
// The fetched roles are handed to the interactive form; roles load
// failure or emptiness renders in place — the form must never submit
// with fabricated role data.
export function PersonCreateLoader() {
  const rolesState = useApiData(getRoles);

  if (rolesState.status === "loading") {
    return <PersonCreateLoading />;
  }

  return (
    <PersonCreateForm
      roles={rolesState.status === "success" ? rolesState.data : undefined}
      rolesError={rolesState.status === "error"}
    />
  );
}
