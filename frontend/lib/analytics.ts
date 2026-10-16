import "server-only"
import { auth } from "@clerk/nextjs/server"
import * as Sentry from "@sentry/nextjs"
import { PostHog } from "posthog-node"

// Product events (spec 32). Sent from the web server only: the browser loads no PostHog code and
// no cookie is set. Every property is an ID or a role; amounts, descriptions, names and emails are
// never sent (AGENTS.md), so each event lists the only keys it may carry.
export const EVENT_KEYS = {
  sign_up_completed: [],
  business_created: ["business_id"],
  bank_connected: ["business_id"],
  minimum_balance_set: ["business_id"],
  dashboard_viewed: ["business_id", "role"],
  alert_opened: ["business_id", "alert_id", "role"],
  alert_dismissed: ["business_id", "alert_id"],
  expected_payment_added: ["business_id"],
} as const satisfies Record<string, readonly PropertyKey[]>

type Keys = typeof EVENT_KEYS
export type EventName = keyof Keys
type Value = { business_id: string; alert_id: string; role: "owner" | "bookkeeper" }
export type EventProperties<E extends EventName> = { [K in Keys[E][number]]: Value[K & keyof Value] }

const DEFAULT_HOST = "https://us.i.posthog.com"
// A slow PostHog must not slow the user's action (AC 12).
const TIMEOUT_MS = 2000

let client: PostHog | null = null

function posthog(): PostHog | null {
  const key = process.env.POSTHOG_KEY
  if (!key) return null
  // flushAt 1 and no interval: a server action may end before a queued batch is sent.
  client ??= new PostHog(key, { host: process.env.POSTHOG_HOST || DEFAULT_HOST, flushAt: 1, flushInterval: 0 })
  return client
}

function withinAllowlist(event: EventName, properties: Record<string, unknown>): boolean {
  const allowed: readonly string[] = EVENT_KEYS[event]
  return Object.keys(properties).every((key) => allowed.includes(key))
}

/**
 * Send one product event for the signed-in user. Never throws and never waits longer than two
 * seconds: a failure goes to Sentry (without the properties) and the caller carries on.
 */
export async function capture<E extends EventName>(event: E, properties: EventProperties<E>): Promise<void> {
  let timer: ReturnType<typeof setTimeout> | undefined
  try {
    if (!withinAllowlist(event, properties)) {
      Sentry.captureMessage(`analytics: ${event} called with a property outside its allowlist`)
      return
    }
    const posthogClient = posthog()
    if (!posthogClient) return
    const { userId } = await auth()
    if (!userId) return
    const timeout = new Promise<void>((resolve) => {
      timer = setTimeout(resolve, TIMEOUT_MS)
    })
    await Promise.race([posthogClient.captureImmediate({ distinctId: userId, event, properties }), timeout])
  } catch (error) {
    Sentry.captureException(error)
  } finally {
    clearTimeout(timer)
  }
}
