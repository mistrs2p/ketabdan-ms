"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Link, useRouter } from "@/i18n/routing";
import {
  createPerson,
  ApiError,
  validationIssues,
  type PersonCreate,
  type RoleRead,
} from "@/lib/api";

// The Create Person form. A Client Component because it owns interactive
// state and submission. Role options arrive from the loader (GET
// /api/roles fetched once, client-side) — they are never hard-coded.
// Roles are selected by checkbox chips (zero/one/many; duplicates
// impossible via the checkbox model) and sent to the backend as
// machine `code`s.
//
// Success navigates back to the People list, which fetches its data
// client-side on mount — the newly created person appears with the
// fresh fetch. No client cache library, no local fabrication of
// success.
export function PersonCreateForm({
  roles,
  rolesError,
}: {
  roles?: RoleRead[];
  rolesError?: boolean;
}) {
  const t = useTranslations("people.create");
  const tPeople = useTranslations("app.pages.people");
  const router = useRouter();

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [active, setActive] = useState(true);
  const [selectedRoleCodes, setSelectedRoleCodes] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [nameError, setNameError] = useState<string | undefined>(undefined);
  const [formError, setFormError] = useState<string | undefined>(undefined);

  const rolesUnavailable = rolesError || !roles || roles.length === 0;

  function toggleRole(code: string) {
    setSelectedRoleCodes((current) =>
      current.includes(code)
        ? current.filter((c) => c !== code)
        : [...current, code],
    );
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting || rolesUnavailable) return;

    // UI-level required check; other field rules stay backend-owned
    // (TBD-D1/D2 — no invented validation).
    const trimmedName = name.trim();
    if (!trimmedName) {
      setNameError(t("validation.nameRequired"));
      setFormError(undefined);
      return;
    }
    setNameError(undefined);

    const payload: PersonCreate = {
      name: trimmedName,
      phone: phone.trim() === "" ? null : phone.trim(),
      active,
      roles: selectedRoleCodes,
    };

    setSubmitting(true);
    setFormError(undefined);
    try {
      await createPerson(payload);
      // The list fetches client-side on mount — a fresh navigation
      // refetches it, so the new person is visible without any cache
      // layer.
      router.push("/people");
    } catch (e) {
      const error =
        e instanceof ApiError ? e : new ApiError("server", String(e));
      if (error.kind === "validation") {
        // Field-level errors where the backend identifies a field
        // (422 loc, e.g. missing name); anything else gets the
        // form-level message with the raw detail kept out of sight.
        const issues = validationIssues(error);
        const nameIssue = issues?.find(
          (issue) =>
            issue.loc.length > 0 &&
            typeof issue.loc[0] === "string" &&
            issue.loc[0] === "body" &&
            issue.loc[1] === "name",
        );
        if (nameIssue) {
          setNameError(t("validation.nameRequired"));
        } else if (typeof error.detail === "string") {
          // Domain error, e.g. unknown role code — shown form-level.
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

      {rolesUnavailable ? (
        <RolesUnavailable error={!!rolesError} />
      ) : (
        <form
          onSubmit={handleSubmit}
          noValidate
          className="flex flex-col gap-5 rounded-lg border border-border bg-surface p-6"
        >
          {/* Name — required */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="person-name" className="text-sm font-medium">
              {t("nameLabel")}
              <span aria-hidden="true" className="text-primary">
                {" *"}
              </span>
            </label>
            <input
              id="person-name"
              name="name"
              type="text"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (nameError) setNameError(undefined);
              }}
              required
              aria-required="true"
              aria-invalid={nameError ? true : undefined}
              aria-describedby={nameError ? "person-name-error" : undefined}
              disabled={submitting}
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
            />
            {nameError ? (
              <p
                id="person-name-error"
                className="text-sm text-primary"
                role="alert"
              >
                {nameError}
              </p>
            ) : null}
          </div>

          {/* Phone — optional, free text (no invented format rules) */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="person-phone" className="text-sm font-medium">
              {t("phoneLabel")}
            </label>
            <input
              id="person-phone"
              name="phone"
              type="text"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              disabled={submitting}
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
            />
            <p className="text-xs text-muted-foreground">{t("phoneHint")}</p>
          </div>

          {/* Roles — zero or more, from live reference data */}
          <fieldset className="flex flex-col gap-2">
            <legend className="text-sm font-medium">{t("rolesLabel")}</legend>
            <p className="text-xs text-muted-foreground">{t("rolesHint")}</p>
            <div className="flex flex-wrap gap-2">
              {roles?.map((role) => {
                const checked = selectedRoleCodes.includes(role.code);
                return (
                  <label
                    key={role.id}
                    className={`inline-flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-1.5 text-sm ${
                      checked
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border text-foreground"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleRole(role.code)}
                      disabled={submitting}
                      className="h-4 w-4 accent-primary"
                    />
                    {role.name}
                  </label>
                );
              })}
            </div>
          </fieldset>

          {/* Active — defaults to true (backend contract) */}
          <div className="flex items-center gap-2">
            <input
              id="person-active"
              name="active"
              type="checkbox"
              checked={active}
              onChange={(e) => setActive(e.target.checked)}
              disabled={submitting}
              className="h-4 w-4 accent-primary"
            />
            <label htmlFor="person-active" className="text-sm font-medium">
              {t("activeLabel")}
            </label>
          </div>

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
              href="/people"
              aria-label={t("cancelBackTo", { page: tPeople("title") })}
              className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-primary/5"
            >
              {t("cancel")}
            </Link>
          </div>
        </form>
      )}
    </div>
  );
}

// Roles could not be loaded or the backend returned none. Submission is
// impossible either way — the form is not rendered at all, so no fake
// role can be sent.
function RolesUnavailable({ error }: { error: boolean }) {
  const t = useTranslations("people.create.rolesError");

  return (
    <div
      className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-6"
      role="alert"
    >
      <h2 className="text-lg font-bold">{t("title")}</h2>
      <p className="text-muted-foreground">
        {error ? t("network") : t("empty")}
      </p>
      <Link
        href="/people"
        className="text-sm font-medium text-primary hover:underline"
      >
        {t("back")}
      </Link>
    </div>
  );
}
