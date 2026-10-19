"use client"

import { useCallback, useState, useTransition } from "react"
import { launchFastLink, type FastLinkLaunch } from "@/app/onboarding/bank/actions"

// Spec 17b. Yodlee's FastLink 4 (https://developer.yodlee.com/docs/fastlink/4.0/getting-started).
const FASTLINK_SCRIPT = "https://cdn.yodlee.com/fastlink/v4/initialize.js"
export const FASTLINK_CONTAINER_ID = "container-fastlink"

type FastLinkSuccess = { providerAccountId?: number | string }
type FastLinkConfig = {
  fastLinkURL: string
  accessToken: string
  params: { configName: string; flow?: "edit"; providerAccountId?: number }
  onSuccess: (data: FastLinkSuccess) => void
  onError: () => void
  onClose: () => void
}
declare global {
  interface Window {
    fastlink?: { open: (config: FastLinkConfig, containerId: string) => void }
  }
}

export type YodleeConnectError = "launchFailed" | "connectFailed" | "alreadyConnected"

function loadScript(): Promise<void> {
  if (window.fastlink) return Promise.resolve()
  return new Promise((resolve, reject) => {
    const script = document.createElement("script")
    script.src = FASTLINK_SCRIPT
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error("fastlink script"))
    document.head.appendChild(script)
  })
}

// Opens FastLink for a business. `onLinked` gets the provider account the owner linked or fixed
// and returns an error to show, or null. The owner logs in on the bank's own screen inside
// FastLink; only the provider account's ID comes back here.
export function useYodleeConnect(
  businessId: string,
  onLinked: (providerAccountId: string) => Promise<YodleeConnectError | null>,
  connectionId?: string,
) {
  const [error, setError] = useState<YodleeConnectError | null>(null)
  const [active, setActive] = useState(false)
  // FastLink's open() throws unless its container is already in the document, and the
  // container renders only once `active` is true: the launch waits here until it is attached.
  const [launch, setLaunch] = useState<FastLinkLaunch | null>(null)
  const [opening, setOpening] = useState(false)
  const [saving, startSaving] = useTransition()

  // The ref callback of the element with `FASTLINK_CONTAINER_ID`. A new launch gives it a new
  // identity, so React calls it again with the mounted element, and FastLink opens there.
  const attachContainer = useCallback(
    (element: HTMLDivElement | null) => {
      if (!element || !launch) return
      setLaunch(null)
      try {
        window.fastlink!.open(
          {
            fastLinkURL: launch.fastlink_url,
            accessToken: `Bearer ${launch.access_token}`,
            params: {
              configName: launch.config_name,
              ...(launch.provider_account_id
                ? { flow: "edit" as const, providerAccountId: Number(launch.provider_account_id) }
                : {}),
            },
            onSuccess: (data) => {
              setActive(false)
              if (data.providerAccountId === undefined) {
                setError("connectFailed")
                return
              }
              startSaving(async () => setError(await onLinked(String(data.providerAccountId))))
            },
            onError: () => {
              setActive(false)
              setError("connectFailed")
            },
            onClose: () => setActive(false),
          },
          FASTLINK_CONTAINER_ID,
        )
      } catch {
        setActive(false)
        setError("launchFailed")
      }
    },
    [launch, onLinked],
  )

  const open = useCallback(async () => {
    setError(null)
    setOpening(true)
    try {
      const result = await launchFastLink(businessId, connectionId)
      if ("error" in result) {
        setError(result.error)
        return
      }
      await loadScript()
      setActive(true)
      setLaunch(result.launch)
    } catch {
      setError("launchFailed")
    } finally {
      setOpening(false)
    }
  }, [businessId, connectionId])

  return { open, attachContainer, pending: opening || saving, active, error, clearError: () => setError(null) }
}
