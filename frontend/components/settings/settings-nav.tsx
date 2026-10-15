"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useTranslations } from "next-intl"

const SECTIONS = [
  { href: "/settings/business", key: "business", ownerOnly: true },
  { href: "/settings/banks", key: "banks", ownerOnly: true },
  { href: "/settings/members", key: "members", ownerOnly: true },
  { href: "/settings/email", key: "email", ownerOnly: false },
  { href: "/settings/data", key: "data", ownerOnly: false },
] as const

// The settings sections (design/mockups/settings-banks.dc.html): a column beside the section on
// desktop, wrapped links above it on a phone.
// A bookkeeper (spec 31) is not shown the sections the API refuses them.
export function SettingsNav({ role = "owner" }: { role?: string }) {
  const t = useTranslations("Settings")
  const pathname = usePathname()

  return (
    <nav aria-label={t("navLabel")} className="lg:w-60 lg:shrink-0">
      <ul className="flex flex-wrap gap-1 lg:flex-col">
        {SECTIONS.filter(({ ownerOnly }) => role === "owner" || !ownerOnly).map(({ href, key }) => (
          <li key={href}>
            <Link
              href={href}
              aria-current={pathname === href ? "page" : undefined}
              className="flex min-h-11 items-center rounded-[10px] px-3.5 text-[15px] font-medium text-ink-2 transition-colors hover:bg-surface-muted aria-[current=page]:bg-surface-active aria-[current=page]:font-semibold aria-[current=page]:text-ink"
            >
              {t(`sections.${key}`)}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  )
}
