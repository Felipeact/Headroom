import { useTranslations } from "next-intl"
import { upcomingDescription } from "@/components/dashboard/copy"
import type { Dashboard } from "@/components/dashboard/types"
import { cn } from "cn"
import { formatDate, formatSignedMoney } from "@/lib/format"

type Item = Dashboard["upcoming"][number]

const HEAD = "px-3 py-2.5 text-xs font-semibold tracking-[0.06em] text-ink-3 uppercase border-b border-border"
const CELL = "px-3 py-3.5 border-b border-surface-muted"

// "Next 14 days" (AC 23, AC 24): a table from `lg` up, a list on phones.
export function UpcomingList({ dashboard }: { dashboard: Dashboard }) {
  const t = useTranslations("Dashboard.upcoming")
  const accountName = new Map(dashboard.accounts.map((a) => [a.id, a.name]))
  const items = dashboard.upcoming

  function description(item: Item): string {
    const d = upcomingDescription(item)
    return "card" in d ? t("cardPayment", { card: d.card }) : d.text
  }
  function type(item: Item): string {
    if (item.source === "card_payment") return t("types.card")
    if (item.source === "expected_payment") return t("types.expected")
    return item.schedule ? t(`types.${item.schedule}`) : t("types.expected")
  }
  const amountClass = (item: Item) =>
    cn("text-right font-semibold tabular-nums", item.amount_cents > 0 && "text-positive")

  return (
    <section
      aria-labelledby="upcoming-title"
      className="flex flex-col gap-3 rounded-[14px] border border-border bg-surface px-4 py-5 sm:px-6"
    >
      <h2 id="upcoming-title" className="text-lg font-semibold">
        {t("title")}
      </h2>
      {items.length === 0 ? (
        <p className="text-sm text-ink-2">{t("empty")}</p>
      ) : (
        <>
          <table data-testid="upcoming-table" className="w-full border-collapse text-[15px] max-lg:hidden">
            <thead>
              <tr>
                <th scope="col" className={`${HEAD} text-left`}>
                  {t("columns.date")}
                </th>
                <th scope="col" className={`${HEAD} text-left`}>
                  {t("columns.description")}
                </th>
                <th scope="col" className={`${HEAD} text-left`}>
                  {t("columns.account")}
                </th>
                <th scope="col" className={`${HEAD} text-left`}>
                  {t("columns.type")}
                </th>
                <th scope="col" className={`${HEAD} text-right`}>
                  {t("columns.amount")}
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td className={`${CELL} whitespace-nowrap`}>{formatDate(item.date, "weekday")}</td>
                  <td data-user-content className={CELL}>
                    {description(item)}
                  </td>
                  <td data-user-content className={CELL}>
                    {accountName.get(item.account_id) ?? ""}
                  </td>
                  <td className={`${CELL} text-ink-2`}>{type(item)}</td>
                  <td className={cn(CELL, amountClass(item))}>{formatSignedMoney(item.amount_cents, item.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <ul data-testid="upcoming-list" className="flex flex-col lg:hidden">
            {items.map((item) => (
              <li
                key={item.id}
                className="flex items-start justify-between gap-3 border-b border-surface-muted py-3 last:border-b-0"
              >
                <div className="flex min-w-0 flex-col gap-0.5">
                  <p data-user-content className="text-[13px] text-ink-3">
                    {t("dateAccount", {
                      date: formatDate(item.date, "weekday"),
                      account: accountName.get(item.account_id) ?? "",
                    })}
                  </p>
                  <p data-user-content className="text-[15px] font-semibold">
                    {description(item)}
                  </p>
                  <p className="text-[13px] text-ink-2">{type(item)}</p>
                </div>
                <p className={amountClass(item)}>{formatSignedMoney(item.amount_cents, item.currency)}</p>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
