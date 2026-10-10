import type { Dashboard } from "@/components/dashboard/types"
import { formatDate } from "@/lib/format"

type Alert = Dashboard["alerts"][number]
type Item = Dashboard["upcoming"][number]

const LOCALE = "en-CA"

/** "Saturday, September 26" or "December 27" for a plain date. */
export function longDate(isoDate: string, weekday: boolean): string {
  const [year, month, day] = isoDate.split("-").map(Number)
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "UTC",
    month: "long",
    day: "numeric",
    ...(weekday ? { weekday: "long" } : {}),
  }).format(new Date(Date.UTC(year, month - 1, day)))
}

/** The oldest sync of the connections, or null while one never synced (AC 11). */
export function oldestSync(connections: Dashboard["connections"]): string | null {
  if (connections.length === 0 || connections.some((c) => c.last_synced_at === null)) return null
  return connections
    .map((c) => c.last_synced_at as string)
    .reduce((a, b) => (new Date(a) <= new Date(b) ? a : b))
}

export type SyncWhen = { kind: "today" | "yesterday" | "on"; day: string; time: string }

/** When a sync happened, relative to `now`, in the business's time zone (AC 11). */
export function syncWhen(isoDateTime: string, timeZone: string, now: Date): SyncWhen {
  const moment = new Date(isoDateTime)
  const ymd = new Intl.DateTimeFormat(LOCALE, { timeZone, year: "numeric", month: "2-digit", day: "2-digit" })
  // en-CA writes "6:02 a.m."; DESIGN.md writes "6:02 AM".
  const time = new Intl.DateTimeFormat("en-US", { timeZone, hour: "numeric", minute: "2-digit" }).format(moment)
  const day = new Intl.DateTimeFormat(LOCALE, { timeZone, month: "short", day: "numeric" }).format(moment)
  const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000)
  if (ymd.format(moment) === ymd.format(now)) return { kind: "today", day, time }
  if (ymd.format(moment) === ymd.format(yesterday)) return { kind: "yesterday", day, time }
  return { kind: "on", day, time }
}

/** "Operating + Reserve": the first word of each account's name. */
export function shortNames(names: string[]): string {
  return names.map((name) => name.split(" ")[0]).join(" + ")
}

/**
 * Who a payment is to or from, on the alert card (AC 15, AC 16): its counterparty, else its
 * description up to the first comma. Expected payments have no counterparty, so "Birch & Co,
 * invoice 1057" reads "Birch & Co" (user decision 2026-10-10).
 */
export function itemName(item: { counterparty: string | null; description: string | null }): string {
  return item.counterparty ?? (item.description ?? "").split(",")[0].trim()
}

/** The alert's causes, largest first (AC 15). */
export function causesBySize(alert: Alert): Alert["items"] {
  return alert.items
    .filter((i) => i.kind === "cause")
    .sort((a, b) => Math.abs(b.amount_cents) - Math.abs(a.amount_cents))
}

/** The week label used on screen: "Nov 9". */
export function weekLabel(isoDate: string): string {
  return formatDate(isoDate)
}

/** A next-14-days row's description (AC 23). */
export function upcomingDescription(item: Item): { card: string } | { text: string } {
  if (item.source === "card_payment") return { card: item.description ?? item.counterparty ?? "" }
  return { text: item.description ?? item.counterparty ?? "" }
}
