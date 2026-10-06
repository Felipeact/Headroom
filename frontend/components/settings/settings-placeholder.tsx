import { useTranslations } from "next-intl"

type Section = "business" | "members" | "email" | "data"

// A settings section whose spec has not been built yet (spec 17).
export function SettingsPlaceholder({ section }: { section: Section }) {
  const t = useTranslations()

  return (
    <div className="flex flex-col gap-1.5">
      <h2 className="text-[22px] font-semibold">{t(`Settings.sections.${section}`)}</h2>
      <p className="text-[15px] text-ink-2">{t("Pages.comingSoon")}</p>
    </div>
  )
}
