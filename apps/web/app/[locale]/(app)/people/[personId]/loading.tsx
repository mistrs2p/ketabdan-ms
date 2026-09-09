import { PeopleLoading } from "@/components/people/PeopleLoading";

// Streaming loading UI for the Person detail route — Next.js shows this
// while the page's server component awaits getPersons().
export default function Loading() {
  return <PeopleLoading />;
}
