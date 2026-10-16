"use client"

import { useCallback, useState, useTransition } from "react"
import { usePlaidLink, type PlaidLinkError } from "react-plaid-link"
import { connectBank, type ConnectBankError, type ConnectBankReturn } from "@/app/onboarding/bank/actions"

// Plaid Link and the connect action, shared by onboarding step 3 (spec 12), "Connect another
// bank" on the choose-accounts step (spec 13) and bank settings (spec 17). The owner logs in on
// the bank's own screen inside Link; only the public token comes back here.
export function useConnectBank(
  businessId: string,
  linkToken: string,
  returnTo: ConnectBankReturn = "/onboarding/accounts",
) {
  const [error, setError] = useState<ConnectBankError | null>(null)
  const [pending, startTransition] = useTransition()

  const onSuccess = useCallback(
    (publicToken: string | null) => {
      if (!publicToken) {
        setError("connectFailed")
        return
      }
      setError(null)
      startTransition(async () => {
        const result = await connectBank(businessId, publicToken, returnTo)
        setError(result.error)
      })
    },
    [businessId, returnTo],
  )
  // Closing Link is not an error; Link reporting one is.
  const onExit = useCallback((linkError: PlaidLinkError | null) => {
    setError(linkError ? "connectFailed" : null)
  }, [])
  const { open, ready } = usePlaidLink({ token: linkToken, onSuccess, onExit })

  return { open, ready, pending, error, clearError: () => setError(null) }
}
