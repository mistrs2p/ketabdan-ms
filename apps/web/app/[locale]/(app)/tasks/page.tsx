import { getTranslations } from "next-intl/server";
import type { Metadata } from "next";
import { PlaceholderPage } from "@/components/layout/PlaceholderPage";

type Props = { params: Promise<{ locale: string }> };

// Tab title from the existing app.pages.tasks.title message.
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "app.pages.tasks" });
  return { title: t("title") };
}

export default function TasksPage({ params }: Props) {
  return <PlaceholderPage params={params} pageKey="tasks" />;
}
