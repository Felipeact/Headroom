import { useTranslations } from "next-intl"

type NavKey = "dashboard" | "expectedPayments" | "alerts" | "settings"

// The empty page each nav link leads to until its own spec fills it in.
export function PlaceholderPage({ titleKey }: { titleKey: NavKey }) {
  const t = useTranslations()

  return (
    <div className="flex flex-col gap-1">
      <h1 className="font-heading text-[30px] font-semibold tracking-[-0.02em] sm:text-[40px]">
        {t(`Nav.${titleKey}`)}
      </h1>
      <p className="text-sm text-ink-2">{t("Pages.comingSoon")}</p>
    </div>
  )
}
