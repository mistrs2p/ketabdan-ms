import { setRequestLocale } from "next-intl/server";
import { AppShell } from "@/components/layout/AppShell";

export default async function AppGroupLayout({
  children,
  params,
}: Readonly<{
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}>) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <AppShell>{children}</AppShell>;
}
