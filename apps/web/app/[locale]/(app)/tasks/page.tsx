import { PlaceholderPage } from "@/components/layout/PlaceholderPage";

type Props = { params: Promise<{ locale: string }> };

export default function TasksPage({ params }: Props) {
  return <PlaceholderPage params={params} pageKey="tasks" />;
}
