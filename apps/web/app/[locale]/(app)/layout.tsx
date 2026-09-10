import { setRequestLocale } from "next-intl/server";
import { AppShell } from "@/components/layout/AppShell";
import { AuthGate } from "@/components/auth/AuthGate";

// The (app) route group = the authenticated application. One guard at
// this layout protects every business page (Task 5.4); `/login` lives
// outside the group and stays public. The gate is the client boundary
// (the token lives in localStorage) — server children stay as they
// were, but are never rendered while unauthenticated.
export default async function AppGroupLayout({
  children,
  params,
}: Readonly<{
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}>) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <AuthGate>
      <AppShell>{children}</AppShell>
    </AuthGate>
  );
}
