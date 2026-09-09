import { getTranslations } from "next-intl/server";
import { apiErrorMessage, type ApiError } from "@/lib/api";

// Error state for the Events list. Uses the ApiError abstraction:
// network vs server failures get distinct, actionable messages; no
// stack traces or technical detail leak beyond the classified message.
export async function EventsErrorState({ error }: { error: ApiError }) {
  const t = await getTranslations("events.error");

  const message = error.kind === "network" ? t("network") : t("server");

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
