"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Link, useRouter } from "@/i18n/routing";
import { createEvent, ApiError, validationIssues, type EventCreate } from "@/lib/api";

// The Create Event form. A Client Component because it owns interactive
// state and submission. Fields are exactly the backend EventCreate
// contract: title (required), type (required, free text — no
// hard-coded selector, the taxonomy is TBD-D5), planned_at (required,
// timezone-aware). No status control: creation always produces DRAFT
// server-side, and the frontend never sends one.
//
// Datetime handling: the datetime-local input yields a naive local
// string; on submit it is converted with the user's current browser
// offset into an ISO-8601 instant WITH explicit offset (e.g.
// "2026-09-20T17:00:00+03:30") — the backend rejects naive values
// (422). This is a technical serialization choice, not a business
// timezone rule. Past dates are NOT rejected (TBD-D27 — no invented
// rule).
export function EventCreateForm() {
  const t = useTranslations("events.create");
  const tEvents = useTranslations("app.pages.events");
  const router = useRouter();

  const [title, setTitle] = useState("");
  const [type, setType] = useState("");
  const [plannedAt, setPlannedAt] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<{
    title?: string;
    type?: string;
    plannedAt?: string;
  }>({});
  const [formError, setFormError] = useState<string | undefined>(undefined);

  function clearFieldError(field: keyof typeof fieldErrors) {
    setFieldErrors((current) => {
      if (current[field] === undefined) return current;
      const next = { ...current };
      delete next[field];
      return next;
    });
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;

    // UI-level required checks; other field rules stay backend-owned
    // (TBD-D25/D26/D27 — no invented validation).
    const errors: typeof fieldErrors = {};
    if (title.trim() === "") errors.title = t("validation.titleRequired");
    if (type.trim() === "") errors.type = t("validation.typeRequired");
    if (plannedAt === "") errors.plannedAt = t("validation.plannedAtRequired");
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      setFormError(undefined);
      return;
    }
    setFieldErrors({});

    // Serialize to a timezone-aware ISO-8601 instant: parse the naive
    // local datetime, then emit it with the browser's current offset.
    // toISOString() would silently convert to UTC (still valid, but
    // the explicit-offset form keeps the wall-clock the user entered).
    const localDate = new Date(plannedAt);
    const payload: EventCreate = {
      title: title.trim(),
      type: type.trim(),
      planned_at: formatWithLocalOffset(localDate),
    };

    setSubmitting(true);
    setFormError(undefined);
    try {
      await createEvent(payload);
      // The list is force-dynamic — a fresh navigation refetches it,
      // so the new event is visible without any cache layer.
      router.push("/events");
    } catch (e) {
      const error =
        e instanceof ApiError ? e : new ApiError("server", String(e));
      if (error.kind === "validation") {
        // Field-level errors where the backend identifies a field
        // (422 loc, e.g. missing title or naive planned_at);
        // anything else gets the form-level message.
        const issues = validationIssues(error);
        const field = issues?.find(
          (issue) =>
            issue.loc.length > 1 &&
            typeof issue.loc[0] === "string" &&
            issue.loc[0] === "body",
        );
        if (field) {
          const name = field.loc[1];
          if (name === "title") {
            setFieldErrors({ title: t("validation.titleRequired") });
          } else if (name === "type") {
            setFieldErrors({ type: t("validation.typeRequired") });
          } else if (name === "planned_at") {
            setFieldErrors({ plannedAt: t("validation.plannedAtInvalid") });
          } else {
            setFormError(t("error.validation"));
          }
        } else if (typeof error.detail === "string") {
          setFormError(error.detail);
        } else {
          setFormError(t("error.validation"));
        }
      } else if (error.kind === "network") {
        setFormError(t("error.network"));
      } else {
        setFormError(t("error.server"));
      }
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <p className="text-muted-foreground">{t("description")}</p>
      </header>

      <form
        onSubmit={handleSubmit}
        noValidate
        className="flex flex-col gap-5 rounded-lg border border-border bg-surface p-6"
      >
        {/* Title — required */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="event-title" className="text-sm font-medium">
            {t("titleLabel")}
            <span aria-hidden="true" className="text-primary">
              {" *"}
            </span>
          </label>
          <input
            id="event-title"
            name="title"
            type="text"
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              clearFieldError("title");
            }}
            required
            aria-required="true"
            aria-invalid={fieldErrors.title ? true : undefined}
            aria-describedby={fieldErrors.title ? "event-title-error" : undefined}
            disabled={submitting}
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
          {fieldErrors.title ? (
            <p id="event-title-error" className="text-sm text-primary" role="alert">
              {fieldErrors.title}
            </p>
          ) : null}
        </div>

        {/* Type — required, free text (no selector; taxonomy TBD-D5) */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="event-type" className="text-sm font-medium">
            {t("typeLabel")}
            <span aria-hidden="true" className="text-primary">
              {" *"}
            </span>
          </label>
          <input
            id="event-type"
            name="type"
            type="text"
            value={type}
            onChange={(e) => {
              setType(e.target.value);
              clearFieldError("type");
            }}
            required
            aria-required="true"
            aria-invalid={fieldErrors.type ? true : undefined}
            aria-describedby={fieldErrors.type ? "event-type-error" : undefined}
            disabled={submitting}
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
          {fieldErrors.type ? (
            <p id="event-type-error" className="text-sm text-primary" role="alert">
              {fieldErrors.type}
            </p>
          ) : null}
          <p className="text-xs text-muted-foreground">{t("typeHint")}</p>
        </div>

        {/* Planned at — required, timezone-aware (serialized on submit) */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="event-planned-at" className="text-sm font-medium">
            {t("plannedAtLabel")}
            <span aria-hidden="true" className="text-primary">
              {" *"}
            </span>
          </label>
          <input
            id="event-planned-at"
            name="planned_at"
            type="datetime-local"
            value={plannedAt}
            onChange={(e) => {
              setPlannedAt(e.target.value);
              clearFieldError("plannedAt");
            }}
            required
            aria-required="true"
            aria-invalid={fieldErrors.plannedAt ? true : undefined}
            aria-describedby={
              fieldErrors.plannedAt ? "event-planned-at-error" : undefined
            }
            disabled={submitting}
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
          {fieldErrors.plannedAt ? (
            <p
              id="event-planned-at-error"
              className="text-sm text-primary"
              role="alert"
            >
              {fieldErrors.plannedAt}
            </p>
          ) : null}
          <p className="text-xs text-muted-foreground">{t("plannedAtHint")}</p>
        </div>

        {/* No status selector: creation always produces DRAFT
            server-side (docs/06 §4c). */}

        {formError ? (
          <p className="rounded-lg border border-border p-3 text-sm" role="alert">
            {formError}
          </p>
        ) : null}

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? t("submitting") : t("submit")}
          </button>
          <Link
            href="/events"
            aria-label={t("cancelBackTo", { page: tEvents("title") })}
            className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-primary/5"
          >
            {t("cancel")}
          </Link>
        </div>
      </form>
    </div>
  );
}

// Serialize a Date as ISO-8601 with the browser's local offset, e.g.
// "2026-09-20T17:00:00+03:30". Never emits a naive string; if the
// offset is zero, emits an explicit "Z". Technical serialization —
// the instant itself is the user's chosen wall-clock time.
function formatWithLocalOffset(date: Date): string {
  const pad = (n: number) => String(Math.abs(n)).padStart(2, "0");
  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const offset = `${sign}${pad(Math.floor(Math.abs(offsetMinutes) / 60))}:${pad(Math.abs(offsetMinutes) % 60)}`;
  const iso = `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}T${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}:${pad(date.getUTCSeconds())}`;
  return offsetMinutes === 0 ? `${iso}Z` : `${iso}${offset}`;
}
