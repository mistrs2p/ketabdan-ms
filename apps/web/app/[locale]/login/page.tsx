import { getTranslations, setRequestLocale } from "next-intl/server";
import { LoginForm } from "@/components/auth/LoginForm";

type Props = {
  params: Promise<{ locale: string }>;
};

// The login page. It lives outside the (app) group — no app shell is
// rendered for an unauthenticated visitor; the page is its own centered
// card with the language switch and theme toggle only. Server component
// for the translated static shell; the interactive form is the client
// boundary (LoginForm).
export default async function LoginPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations("login");

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-background p-4 text-foreground">
      <main className="w-full max-w-sm">
        <h1 className="mb-6 text-center text-2xl font-bold">{t("title")}</h1>
        <LoginForm />
      </main>
    </div>
  );
}
