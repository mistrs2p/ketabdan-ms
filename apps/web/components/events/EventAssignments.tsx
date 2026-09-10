"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  createEventAssignment,
  getEventAssignments,
  ApiError,
  validationIssues,
  type EventAssignmentRead,
  type PersonRead,
  type EventAssignmentCreate,
} from "@/lib/api";
import {
  KNOWN_RESPONSIBILITY_CODES,
  responsibilityLabel,
  approvalStatusLabel,
} from "./assignmentLabels";

// The Event Assignments section of the event detail screen. A Client
// Component because creating an assignment is interactive: the form
// owns selection state and submission, and the visible list is updated
// from the backend's own response — never a fabricated local row.
//
// Data flow (server page → this component):
//   - initial assignments: GET /api/event-assignments, filtered to this
//     event client-side (no dedicated /events/{id}/assignments endpoint
//     exists — docs/06 §4d is the contract);
//   - people: GET /api/persons (ordered by name — backend ordering is
//     preserved, the UI never re-sorts).
// After a successful create, the list is refreshed with a fresh
// getEventAssignments() call — the backend response is the source of
// truth, and the new row appears immediately without a full reload.
//
// No approval controls: approval_status is displayed as returned
// (PROVISIONAL set, TBD-D10/A6); the approval workflow is defined but
// unimplemented (docs/06 §4e) — this task is read/create only.
export function EventAssignments({
  eventId,
  initialAssignments,
  people,
}: {
  eventId: string;
  initialAssignments: EventAssignmentRead[];
  people: PersonRead[];
}) {
  const t = useTranslations("events.assignments");
  const [assignments, setAssignments] = useState(initialAssignments);
  const [refreshError, setRefreshError] = useState(false);

  async function refresh() {
    // Re-fetch the full list and filter to this event — same call the
    // server page made, so the shape and ordering cannot diverge.
    try {
      const all = await getEventAssignments();
      setAssignments(all.filter((a) => a.event_id === eventId));
      setRefreshError(false);
    } catch {
      // The create itself succeeded; only the refresh failed. The new
      // row is still shown optimistically from the create response.
      setRefreshError(true);
    }
  }

  const responsibilityLabels: Record<string, string> = {};
  for (const code of KNOWN_RESPONSIBILITY_CODES) {
    responsibilityLabels[code] = t(`responsibility.${code}`);
  }
  const approvalLabels: Record<string, string> = {
    PENDING: t("approval.PENDING"),
    APPROVED: t("approval.APPROVED"),
  };

  return (
    <section className="flex flex-col gap-4" aria-labelledby="event-assignments-heading">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="event-assignments-heading" className="text-lg font-bold">
          {t("title")}
        </h2>
        <p className="text-sm text-muted-foreground">{t("description")}</p>
      </div>

      {refreshError ? (
        <p className="text-sm text-muted-foreground" role="status">
          {t("refreshError")}
        </p>
      ) : null}

      <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
        {/* Assignment list — person, responsibility, status */}
        <div className="flex w-full flex-col gap-3 lg:flex-1">
          {assignments.length === 0 ? (
            <div
              className="flex flex-col gap-1 rounded-lg border border-dashed border-border p-6 text-center"
              role="status"
            >
              <p className="text-sm font-medium">{t("empty.title")}</p>
              <p className="text-sm text-muted-foreground">{t("empty.description")}</p>
            </div>
          ) : (
            <ul className="flex flex-col gap-3">
              {assignments.map((assignment) => {
                const person = people.find((p) => p.id === assignment.person_id);
                return (
                  <li
                    key={assignment.id}
                    className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-4 sm:flex-row sm:items-center sm:justify-between sm:gap-4"
                  >
                    <div className="flex flex-col gap-0.5 min-w-0">
                      {/* Person name as the primary label — never a raw id.
                          If the person is missing from the fetched list
                          (e.g. created after page load), still show a
                          readable fallback rather than an id. */}
                      <span className="truncate text-sm font-medium">
                        {person ? person.name : t("unknownPerson")}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {responsibilityLabel(
                          assignment.responsibility.code,
                          responsibilityLabels,
                          assignment.responsibility.name,
                        )}
                      </span>
                    </div>
                    <span className="inline-flex w-fit items-center gap-1.5 rounded bg-primary/10 px-2 py-0.5 text-xs text-primary">
                      {/* Status is carried by the localized text label;
                          unknown values fall back to the raw value. */}
                      <span
                        aria-hidden="true"
                        className="h-1.5 w-1.5 rounded-full bg-primary"
                      />
                      {approvalStatusLabel(
                        assignment.approval_status,
                        approvalLabels,
                      )}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Create form — people and responsibility, nothing else */}
        <div className="w-full lg:max-w-sm">
          <AssignmentCreateForm
            eventId={eventId}
            people={people}
            responsibilityLabels={responsibilityLabels}
            onCreated={refresh}
          />
        </div>
      </div>
    </section>
  );
}

// The assignment creation form. Fields are exactly the backend
// EventAssignmentCreate contract: person (by UUID value) and
// responsibility (by stable machine code). No approval input —
// creation always produces PENDING server-side (docs/06 §4d) and the
// frontend never sends one.
//
// The UI does not filter people by active/roles: no such restriction
// exists in the backend contract (TBD-D3/D8) and inventing one here
// would fake a business rule.
function AssignmentCreateForm({
  eventId,
  people,
  responsibilityLabels,
  onCreated,
}: {
  eventId: string;
  people: PersonRead[];
  responsibilityLabels: Record<string, string>;
  onCreated: () => Promise<void>;
}) {
  const t = useTranslations("events.assignments.create");
  const tPeople = useTranslations("people");

  const [personId, setPersonId] = useState("");
  const [responsibility, setResponsibility] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [personError, setPersonError] = useState<string | undefined>(undefined);
  const [responsibilityError, setResponsibilityError] = useState<
    string | undefined
  >(undefined);
  const [formError, setFormError] = useState<string | undefined>(undefined);

  function resetFieldErrors() {
    setPersonError(undefined);
    setResponsibilityError(undefined);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;

    // UI-level required checks only — every other rule (unknown
    // references, duplicates/TBD-D11, inactive persons/TBD-D3, …) is
    // backend-owned and never pre-validated here.
    const errors: { person?: string; responsibility?: string } = {};
    if (personId === "") errors.person = t("personRequired");
    if (responsibility === "") errors.responsibility = t("responsibilityRequired");
    if (errors.person || errors.responsibility) {
      setPersonError(errors.person);
      setResponsibilityError(errors.responsibility);
      setFormError(undefined);
      return;
    }
    resetFieldErrors();

    const payload: EventAssignmentCreate = {
      event_id: eventId,
      person_id: personId,
      responsibility,
    };

    setSubmitting(true);
    setFormError(undefined);
    try {
      await createEventAssignment(payload);
      // Success: reset the form, confirm, and refresh the list from
      // the backend — no local fabrication of the new row.
      setPersonId("");
      setResponsibility("");
      setSuccess(true);
      await onCreated();
    } catch (e) {
      const error =
        e instanceof ApiError ? e : new ApiError("server", String(e));
      if (error.kind === "validation") {
        // Field-level 422s where the backend identifies a field;
        // domain errors (unknown responsibility code) arrive as a
        // string detail and are shown form-level, verbatim — never
        // swallowed, never rewritten into a fake success.
        const issues = validationIssues(error);
        const field = issues?.find(
          (issue) =>
            issue.loc.length > 1 &&
            typeof issue.loc[0] === "string" &&
            issue.loc[0] === "body",
        );
        const name = field?.loc[1];
        if (name === "person_id") {
          setPersonError(t("personRequired"));
        } else if (name === "responsibility") {
          setResponsibilityError(t("responsibilityRequired"));
        } else if (typeof error.detail === "string") {
          setFormError(error.detail);
        } else {
          setFormError(t("error.validation"));
        }
      } else if (error.kind === "network") {
        setFormError(t("error.network"));
      } else {
        // 404 (event/person deleted server-side) and anything else.
        setFormError(
          typeof error.detail === "string" ? error.detail : t("error.server"),
        );
      }
      setSuccess(false);
    } finally {
      setSubmitting(false);
    }
  }

  if (people.length === 0) {
    // No people exist at all — the form cannot be built safely (the
    // selector would offer nothing), so render the empty state instead.
    return (
      <div
        className="flex flex-col gap-2 rounded-lg border border-dashed border-border p-5"
        role="status"
      >
        <h3 className="text-sm font-medium">{t("noPeople.title")}</h3>
        <p className="text-sm text-muted-foreground">{t("noPeople.description")}</p>
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-5"
    >
      <h3 className="text-sm font-medium">{t("title")}</h3>

      {/* Person — required; name is the primary label, phone optional context */}
      <div className="flex flex-col gap-1.5">
        <label htmlFor="assignment-person" className="text-sm font-medium">
          {t("personLabel")}
          <span aria-hidden="true" className="text-primary">
            {" *"}
          </span>
        </label>
        <select
          id="assignment-person"
          name="person_id"
          value={personId}
          onChange={(e) => {
            setPersonId(e.target.value);
            if (personError) setPersonError(undefined);
          }}
          required
          aria-required="true"
          aria-invalid={personError ? true : undefined}
          aria-describedby={personError ? "assignment-person-error" : undefined}
          disabled={submitting}
          className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
        >
          <option value="">{t("personPlaceholder")}</option>
          {people.map((person) => (
            <option key={person.id} value={person.id}>
              {person.name}
              {person.phone ? ` — ${person.phone}` : ""}
            </option>
          ))}
        </select>
        {personError ? (
          <p id="assignment-person-error" className="text-sm text-primary" role="alert">
            {personError}
          </p>
        ) : null}
      </div>

      {/* Responsibility — required; the six seeded codes, localized */}
      <div className="flex flex-col gap-1.5">
        <label htmlFor="assignment-responsibility" className="text-sm font-medium">
          {t("responsibilityLabel")}
          <span aria-hidden="true" className="text-primary">
            {" *"}
          </span>
        </label>
        <select
          id="assignment-responsibility"
          name="responsibility"
          value={responsibility}
          onChange={(e) => {
            setResponsibility(e.target.value);
            if (responsibilityError) setResponsibilityError(undefined);
          }}
          required
          aria-required="true"
          aria-invalid={responsibilityError ? true : undefined}
          aria-describedby={
            responsibilityError ? "assignment-responsibility-error" : undefined
          }
          disabled={submitting}
          className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
        >
          <option value="">{t("responsibilityPlaceholder")}</option>
          {KNOWN_RESPONSIBILITY_CODES.map((code) => (
            <option key={code} value={code}>
              {responsibilityLabels[code]}
            </option>
          ))}
        </select>
        {responsibilityError ? (
          <p
            id="assignment-responsibility-error"
            className="text-sm text-primary"
            role="alert"
          >
            {responsibilityError}
          </p>
        ) : null}
        {/* The backend value is the machine code; the label is display-only. */}
        <p className="text-xs text-muted-foreground">{t("responsibilityHint")}</p>
      </div>

      {/* No approval input: creation always produces PENDING
          server-side (docs/06 §4d). */}

      {success && !formError ? (
        <p className="rounded-lg bg-primary/10 px-3 py-2 text-sm text-primary" role="status">
          {t("success")}
        </p>
      ) : null}

      {formError ? (
        <p className="rounded-lg border border-border p-3 text-sm" role="alert">
          {formError}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={submitting}
        className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? t("submitting") : t("submit")}
      </button>

      <p className="text-xs text-muted-foreground">
        {t("peopleCount", { count: people.length })}
        {people.some((p) => !p.active)
          ? ` · ${tPeople("status.inactive")}: ${people.filter((p) => !p.active).length}`
          : ""}
      </p>
    </form>
  );
}
