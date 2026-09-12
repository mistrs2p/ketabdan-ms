"use client";

import { useTranslations } from "next-intl";
import { apiErrorMessage, type ApiError } from "@/lib/api";

// Error state for the People list. Uses the Task-4.1 ApiError
// abstraction: network vs server failures get distinct, actionable
// messages; 404/422 are not expected on this list endpoint and fall
// back to the generic server wording. No stack traces or technical
// detail leak — only the classified message.
export function PeopleErrorState({ error }: { error: ApiError }) {
  const t = useTranslations("people.error");

  const message =
    error.kind === "network" ? t("network") : t("server");

  return (
    <div
      className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-6"
      role="alert"
    >
      <h2 className="text-lg font-bold">{t("title")}</h2>
      <p className="text-muted-foreground">{message}</p>
      {/* Technical reason — visible on demand for developers, not the
          primary user-facing message. */}
      <details className="text-sm text-muted-foreground">
        <summary className="cursor-pointer select-none">
          {apiErrorMessage(error)}
        </summary>
      </details>
    </div>
  );
}
