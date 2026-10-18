"use client"

import { useCallback, useEffect, useRef, useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import {
  connectFlinksBank,
  type ConnectBankReturn,
  type ConnectFlinksError,
} from "@/app/onboarding/bank/actions"

// Flinks Connect in a dialog (spec 17a). The owner logs in on the bank's own screen inside the
// Flinks iframe, which posts a REDIRECT message carrying the loginId. Only a message from the
// iframe's own origin counts. The iframe's authorize token is single-use, so closing the dialog
// without connecting re-renders the page for a fresh one.
export function useFlinksConnect(
  businessId: string,
  origin: string,
  returnTo: ConnectBankReturn = "/onboarding/accounts",
) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState<ConnectFlinksError | null>(null)
  const [pending, startTransition] = useTransition()
  // Kept for "Try again": Flinks keeps the login while it prepares the accounts.
  const loginId = useRef<string | null>(null)

  const submit = useCallback(
    (id: string) => {
      loginId.current = id
      setError(null)
      startTransition(async () => {
        const result = await connectFlinksBank(businessId, id, returnTo)
        setError(result.error)
        // The iframe spent its single-use token on this login: a later open needs a new one.
        router.refresh()
      })
    },
    [businessId, returnTo, router],
  )

  useEffect(() => {
    if (!open) return
    function onMessage(event: MessageEvent) {
      if (event.origin !== origin) return
      const data: unknown = event.data
      if (typeof data !== "object" || data === null) return
      const { step, url } = data as { step?: unknown; url?: unknown }
      if (step !== "REDIRECT" || typeof url !== "string") return
      let id: string | null = null
      try {
        id = new URL(url).searchParams.get("loginId")
      } catch {
        id = null
      }
      setOpen(false)
      if (id) {
        submit(id)
        return
      }
      setError("connectFailed")
      // The iframe finished, so its token is spent even without a loginId.
      router.refresh()
    }
    window.addEventListener("message", onMessage)
    return () => window.removeEventListener("message", onMessage)
  }, [open, origin, submit, router])

  const onOpenChange = useCallback(
    (next: boolean) => {
      setOpen(next)
      setLoaded(false)
      if (next) setError(null)
      else if (loginId.current === null) router.refresh()
    },
    [router],
  )

  const retry = useCallback(() => {
    if (loginId.current) submit(loginId.current)
  }, [submit])

  return {
    open,
    onOpenChange,
    loaded,
    onLoad: () => setLoaded(true),
    pending,
    error,
    retry,
  }
}
