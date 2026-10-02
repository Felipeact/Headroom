"use client"

import { useTranslations } from "next-intl"
import { MobileMenu } from "./mobile-menu"
import { NavLinks } from "./nav-links"

// The header from design/mockups/dashboard-desktop.dc.html and dashboard-phone.dc.html.
// businessName arrives with spec 11; until then the wordmark stands in for it on phones.
export function AppHeader({ businessName }: { businessName?: string }) {
  const t = useTranslations("Shell")

  return (
    <header className="flex items-center justify-between gap-3 border-b border-border pb-3 lg:gap-6 lg:pb-5">
      <div data-testid="header-desktop-identity" className="hidden items-center gap-5 lg:flex">
        <span className="font-heading text-[22px] font-semibold tracking-[-0.01em]">
          {t("wordmark")}
        </span>
        {businessName && (
          <>
            <div
              data-testid="business-divider"
              aria-hidden="true"
              className="h-8 w-px bg-border-input"
            />
            <div className="flex flex-col gap-0.5">
              <span className="text-xs text-ink-3">{t("businessLabel")}</span>
              <span className="text-[15px] font-semibold">{businessName}</span>
            </div>
          </>
        )}
      </div>
      <span
        data-testid="header-phone-identity"
        className="font-heading text-xl font-semibold tracking-[-0.01em] lg:hidden"
      >
        {businessName ?? t("wordmark")}
      </span>
      <nav aria-label={t("mainNav")} className="hidden lg:block">
        <NavLinks />
      </nav>
      <MobileMenu className="border-border lg:hidden" />
    </header>
  )
}
