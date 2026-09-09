import { PlaceholderPage } from "@/components/layout/PlaceholderPage";

type Props = { params: Promise<{ locale: string }> };

export default function CalendarPage({ params }: Props) {
  return <PlaceholderPage params={params} pageKey="calendar" />;
}
