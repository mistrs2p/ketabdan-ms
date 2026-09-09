import { PlaceholderPage } from "@/components/layout/PlaceholderPage";

type Props = { params: Promise<{ locale: string }> };

export default function EventsPage({ params }: Props) {
  return <PlaceholderPage params={params} pageKey="events" />;
}
