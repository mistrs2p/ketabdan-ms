import { PlaceholderPage } from "@/components/layout/PlaceholderPage";

type Props = { params: Promise<{ locale: string }> };

export default function PeoplePage({ params }: Props) {
  return <PlaceholderPage params={params} pageKey="people" />;
}
