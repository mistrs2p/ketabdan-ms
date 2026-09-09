import { setRequestLocale } from "next-intl/server";
import { getTranslations } from "next-intl/server";

type Props = {
  params: Promise<{ locale: string }>;
  pageKey: string;
};

// Shared placeholder for future section pages — proves shell integration
// and navigation; no domain logic.
export async function PlaceholderPage({ params, pageKey }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations(`app.pages.${pageKey}`);

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <h1 className="text-2xl font-bold">{t("title")}</h1>
      <p className="text-muted-foreground">{t("placeholder")}</p>
    </div>
  );
}
