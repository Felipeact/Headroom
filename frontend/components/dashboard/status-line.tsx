import { CircleCheck } from "lucide-react"
import { useTranslations } from "next-intl"
import { oldestSync, syncWhen } from "@/components/dashboard/copy"
import type { Dashboard } from "@/components/dashboard/types"

// "Updated today at 6:02 AM · 2 banks synced" (AC 11); phones drop "today at".
export function StatusLine({
  connections,
  timeZone,
  now,
}: {
  connections: Dashboard["connections"]
  timeZone: string
  now: string
}) {
  const t = useTranslations("Dashboard")
  const oldest = oldestSync(connections)
  const count = connections.filter((c) => c.last_synced_at !== null).length

  let wide: string
  let narrow: string
  if (oldest === null) {
    wide = narrow = t("statusWaiting")
  } else {
    const when = syncWhen(oldest, timeZone, new Date(now))
    const long =
      when.kind === "today"
        ? t("syncedToday", { time: when.time })
        : when.kind === "yesterday"
          ? t("syncedYesterday", { time: when.time })
          : t("syncedOn", { day: when.day, time: when.time })
    wide = t("status", { when: long, count })
    narrow = when.kind === "today" ? t("status", { when: t("syncedTodayShort", { time: when.time }), count }) : wide
  }

  return (
    <p data-testid="status-line" className="flex items-center gap-2 text-sm text-ink-2">
      <CircleCheck aria-hidden="true" className="size-[18px] shrink-0 text-positive" strokeWidth={2} />
      <span className="max-lg:hidden">{wide}</span>
      <span className="lg:hidden">{narrow}</span>
    </p>
  )
}
