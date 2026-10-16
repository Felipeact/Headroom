import { useTranslations } from "next-intl"

export function SkipLink() {
  const t = useTranslations("Shell")

  return (
    <a
      href="#main"
      className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:flex focus:min-h-11 focus:items-center focus:rounded-[10px] focus:bg-surface focus:px-4 focus:text-[15px] focus:font-semibold focus:text-ink"
    >
      {t("skipToContent")}
    </a>
  )
}
