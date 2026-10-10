import Link from "next/link"
import { TriangleAlert } from "lucide-react"
import { useTranslations } from "next-intl"

// Some bank data is older than 2 days (AC 31). DESIGN.md "Partial": show what's there, and warn.
export function StaleBanner() {
  const t = useTranslations("Dashboard.stale")

  return (
    <div
      role="status"
      className="flex flex-col gap-2 rounded-[10px] border border-warning-border bg-warning-bg px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
    >
      <p className="flex items-start gap-2.5 text-sm leading-[1.45] text-warning-text">
        <TriangleAlert aria-hidden="true" className="mt-px size-5 shrink-0" strokeWidth={1.8} />
        <span>{t("body")}</span>
      </p>
      <Link
        href="/settings/banks"
        className="flex min-h-11 shrink-0 items-center text-sm font-medium text-accent underline underline-offset-4 hover:text-accent-hover"
      >
        {t("action")}
      </Link>
    </div>
  )
}
