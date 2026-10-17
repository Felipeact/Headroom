"use client"

import { useId } from "react"
import { CircleCheck, Landmark } from "lucide-react"
import { useTranslations } from "next-intl"
import type { AccountChange } from "@/app/(app)/settings/banks/actions"
import { AccountRow } from "@/components/settings/account-row"
import { DisconnectDialog } from "@/components/settings/disconnect-dialog"
import { ReconnectBanner } from "@/components/settings/reconnect-banner"
import { Badge } from "@/components/ui/badge"
import { formatSyncedAt } from "@/lib/format"
import type { components } from "@/lib/api/schema"

type Connection = components["schemas"]["Connection"]

const HEAD = "px-3 py-2.5 text-xs font-semibold tracking-[0.06em] text-ink-3 uppercase"

// One bank on Settings > Bank connections (spec 17): its sync status, a banner with "Reconnect"
// when it needs attention, its accounts, and "Disconnect".
export function BankCard({
  businessId,
  connection,
  timeZone,
  now,
  updateToken,
  disabled,
  onChange,
}: {
  businessId: string
  connection: Connection
  timeZone: string
  now: string
  updateToken: string | null
  disabled: boolean
  onChange: (accountId: string, change: AccountChange) => void
}) {
  const t = useTranslations("Settings.Banks")
  const providers = useTranslations("BankProviders")
  const headingId = useId()
  const bank = connection.institution_name
  const attention = connection.status === "login_required" || connection.status === "sync_failing"

  return (
    <section
      aria-labelledby={headingId}
      className={`flex flex-col gap-3 rounded-[14px] border bg-surface p-4 sm:px-6 sm:py-5 ${
        attention ? "border-warning-border" : "border-border"
      }`}
    >
      <div className="flex items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <Landmark aria-hidden="true" className="size-6 shrink-0 text-ink-2" strokeWidth={1.8} />
          <div className="flex min-w-0 flex-col gap-0.5">
            <h3 id={headingId} data-user-content className="text-base font-semibold">
              {bank}
            </h3>
            <p className="text-[13px] text-ink-3">{providers(`via.${connection.provider}`)}</p>
            {attention ? (
              <Badge variant="warning">{t("needsAttention")}</Badge>
            ) : connection.status === "synced" && connection.last_synced_at ? (
              <p data-user-content className="flex items-center gap-1.5 text-[13px] text-positive">
                <CircleCheck aria-hidden="true" className="size-3.5" strokeWidth={2.2} />
                {t("synced", { when: formatSyncedAt(connection.last_synced_at, timeZone, new Date(now)) })}
              </p>
            ) : (
              <p className="text-[13px] text-ink-3">{t("syncing")}</p>
            )}
          </div>
        </div>
        <DisconnectDialog businessId={businessId} connectionId={connection.id} bank={bank} />
      </div>

      {attention && connection.provider === "flinks" && (
        <div
          role="alert"
          className="rounded-[10px] border border-warning-border bg-warning-bg px-4 py-3 text-sm leading-[1.45] text-warning-text"
        >
          <p data-user-content>
            {t(connection.status === "login_required" ? "loginBanner" : "syncFailingBanner", { bank })}{" "}
            {providers("reconnectFlinks")}
          </p>
        </div>
      )}

      {attention && connection.provider !== "flinks" && (
        <ReconnectBanner
          businessId={businessId}
          connectionId={connection.id}
          bank={bank}
          reason={connection.status === "login_required" ? "login" : "failing"}
          updateToken={updateToken}
        />
      )}

      <table className="w-full border-collapse text-[15px]">
        <thead className="max-sm:sr-only">
          <tr>
            <th scope="col" className={`${HEAD} text-left`}>
              {t("columns.account")}
            </th>
            <th scope="col" className={`${HEAD} text-right`}>
              {t("columns.balance")}
            </th>
            <th scope="col" className={`${HEAD} text-left sm:pl-8`}>
              {t("columns.countsAsCash")}
            </th>
            <th scope="col" className={`${HEAD} text-left`}>
              {t("columns.primary")}
            </th>
          </tr>
        </thead>
        <tbody>
          {connection.accounts.map((account) => (
            <AccountRow
              key={account.id}
              account={account}
              disabled={disabled}
              onChange={(change) => onChange(account.id, change)}
            />
          ))}
        </tbody>
      </table>
    </section>
  )
}
