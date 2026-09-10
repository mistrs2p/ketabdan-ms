import { getTranslations, setRequestLocale } from "next-intl/server";
import type { Metadata } from "next";
import { getRoles, type RoleRead } from "@/lib/api";
import { PersonCreateForm } from "@/components/people/PersonCreateForm";

type Props = { params: Promise<{ locale: string }> };

// Live backend reference data — render per request, never at build time.
export const dynamic = "force-dynamic";

// Tab title from the existing people.create.title message.
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "people.create" });
  return { title: t("title") };
}

// Create Person. The page (Server Component) fetches the role reference
// data once and passes it to the client form; the form owns interactive
// state and submission. Roles load failure or emptiness renders in place
// — the form must never submit with fabricated role data.
export default async function Page({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  let roles: RoleRead[] | undefined;
  let rolesError = false;
  try {
    roles = await getRoles();
  } catch {
    // The form cannot be built safely without real reference data —
    // render the role-loading failure state instead of a broken form.
    rolesError = true;
  }

  return <PersonCreateForm roles={roles} rolesError={rolesError} />;
}
