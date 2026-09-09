import { PeopleLoading } from "@/components/people/PeopleLoading";

// Streaming loading UI for the Create Person route — Next.js shows this
// while the page's server component awaits getRoles().
export default function Loading() {
  return <PeopleLoading />;
}
