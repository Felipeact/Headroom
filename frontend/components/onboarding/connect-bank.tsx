"use client"

import { CircleAlert, Eye, Lock, Power, type LucideIcon } from "lucide-react"
import { useTranslations } from "next-intl"
import { useConnectBank } from "@/components/onboarding/use-connect-bank"
import { Button } from "@/components/ui/button"

const TRUST_ITEMS = [
  { icon: Eye, title: "Bank.readOnlyTitle", body: "Bank.readOnlyBody" },
  { icon: Lock, title: "Bank.passwordTitle", body: "Bank.passwordBody" },
  { icon: Power, title: "Bank.controlTitle", body: "Bank.controlBody" },
] as const satisfies readonly { icon: LucideIcon; title: string; body: string }[]

// Onboarding step 3, from design/mockups/onboarding-3-connect-bank.dc.html (spec 12). The owner
// logs in on the bank's own screen inside Plaid Link; only the public token comes back here.
export function ConnectBank({ businessId, linkToken }: { businessId: string; linkToken: string }) {
  const t = useTranslations("Onboarding")
  const { open, ready, pending, error } = useConnectBank(businessId, linkToken)

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="font-heading text-[28px] leading-tight font-semibold tracking-[-0.02em]">
          {t("Bank.title")}
        </h1>
        <p className="text-[15px] leading-normal text-ink-2">{t("Bank.intro")}</p>
      </div>
      <ul className="flex flex-col rounded-[14px] border border-border bg-surface px-4 py-1">
        {TRUST_ITEMS.map(({ icon: Icon, title, body }) => (
          <li
            key={title}
            className="flex items-start gap-3 border-b border-surface-muted py-3.5 last:border-b-0"
          >
            <Icon aria-hidden="true" className="size-[22px] shrink-0 text-accent" strokeWidth={1.8} />
            <div className="flex flex-col gap-[3px]">
              <p className="text-[15px] font-semibold">{t(title)}</p>
              <p className="text-sm leading-[1.45] text-ink-2">{t(body)}</p>
            </div>
          </li>
        ))}
      </ul>
      <p className="text-[13px] text-ink-3">{t("Bank.provider")}</p>
      <div className="mt-auto flex flex-col gap-3">
        <div role="alert">
          {error && (
            <p className="flex items-start gap-1.5 text-sm text-danger-text">
              <CircleAlert aria-hidden="true" className="mt-px size-4 shrink-0" strokeWidth={1.8} />
              <span>{t(`Bank.errors.${error}`)}</span>
            </p>
          )}
        </div>
        <Button
          type="button"
          disabled={!ready || pending}
          aria-busy={pending}
          onClick={() => open()}
          className="min-h-[52px] text-base"
        >
          {pending ? t("Bank.connecting") : t("Bank.connect")}
        </Button>
      </div>
    </div>
  )
}
