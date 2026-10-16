"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useTranslations } from "next-intl"
import { cn } from "cn"

const LINKS = [
  { href: "/", key: "dashboard" },
  { href: "/expected-payments", key: "expectedPayments" },
  { href: "/alerts", key: "alerts" },
  { href: "/settings", key: "settings" },
] as const

export function NavLinks({
  className,
  onNavigate,
}: {
  className?: string
  onNavigate?: () => void
}) {
  const t = useTranslations("Nav")
  const pathname = usePathname()

  return (
    <ul className={cn("flex gap-1", className)}>
      {LINKS.map(({ href, key }) => (
        <li key={href}>
          <Link
            href={href}
            // A section stays current on its own pages, such as /settings/banks (spec 17).
            aria-current={pathname === href || (href !== "/" && pathname.startsWith(`${href}/`)) ? "page" : undefined}
            onClick={onNavigate}
            className="flex min-h-11 items-center rounded-[10px] px-3.5 text-[15px] font-medium text-ink-2 transition-colors hover:bg-surface-muted aria-[current=page]:bg-surface-active aria-[current=page]:font-semibold aria-[current=page]:text-ink"
          >
            {t(key)}
          </Link>
        </li>
      ))}
    </ul>
  )
}
