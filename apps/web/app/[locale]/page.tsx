import { setRequestLocale } from "next-intl/server";
import { getTranslations } from "next-intl/server";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { ThemeToggle } from "@/components/ThemeToggle";

type Props = {
  params: Promise<{ locale: string }>;
};

export default async function FoundationPreviewPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations("foundation");

  return (
    <main className="min-h-dvh bg-background text-foreground">
      <div className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-2xl font-bold">
            {t("title")} — {t("subtitle")}
          </h1>
          <div className="flex items-center gap-2">
            <LocaleSwitcher />
            <ThemeToggle />
          </div>
        </header>

        <p className="text-muted-foreground">{t("statusText")}</p>

        <section className="rounded-xl border border-border bg-surface p-6">
          <h2 className="text-lg font-semibold">{t("card.title")}</h2>
          <p className="mt-2 text-muted-foreground">{t("card.body")}</p>
        </section>

        <div className="flex items-center gap-3">
          <button
            type="button"
            className="rounded-lg bg-primary px-4 py-2 font-medium text-primary-foreground"
          >
            {t("button")}
          </button>
        </div>
      </div>
    </main>
  );
}
