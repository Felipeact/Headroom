"use client"

import { CircleAlert } from "lucide-react"
import { useTranslations } from "next-intl"
import type { ConnectBankReturn } from "@/app/onboarding/bank/actions"
import { useFlinksConnect } from "@/components/onboarding/use-flinks-connect"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import type { FlinksConnect as FlinksConnectInfo } from "@/lib/api/bank"

// "Connect with Flinks" (spec 17a), next to "Connect with Plaid" wherever an owner connects a
// bank: for banks whose sign-in Plaid can't finish, such as RBC with an authenticator app.
export function FlinksConnect({
  businessId,
  flinks,
  returnTo,
  disabled = false,
  className,
}: {
  businessId: string
  flinks: FlinksConnectInfo
  returnTo?: ConnectBankReturn
  disabled?: boolean
  className?: string
}) {
  const providers = useTranslations("BankProviders")
  const connect = useFlinksConnect(businessId, flinks.origin, returnTo)

  return (
    <div className="flex flex-col gap-2">
      <p className="text-[13px] leading-[1.45] text-ink-3">{providers("hint")}</p>
      <Dialog open={connect.open} onOpenChange={connect.onOpenChange}>
        <DialogTrigger asChild>
          <Button
            type="button"
            variant="outline"
            disabled={disabled || connect.pending}
            aria-busy={connect.pending}
            className={className}
          >
            {connect.pending ? providers("connecting") : providers("flinks")}
          </Button>
        </DialogTrigger>
        <DialogContent className="flex max-h-[calc(100dvh-2rem)] flex-col gap-3 sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{providers("dialogTitle")}</DialogTitle>
            <DialogDescription>{providers("dialogDescription")}</DialogDescription>
          </DialogHeader>
          {!connect.loaded && (
            <p role="status" className="text-sm text-ink-2">
              {providers("loading")}
            </p>
          )}
          <iframe
            title={providers("frameTitle")}
            src={flinks.connect_url}
            onLoad={connect.onLoad}
            className="h-[min(640px,70dvh)] w-full rounded-[10px] border border-border"
          />
        </DialogContent>
      </Dialog>
      <div role="alert">
        {connect.error && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <p className="flex items-start gap-1.5 text-sm text-danger-text">
              <CircleAlert aria-hidden="true" className="mt-px size-4 shrink-0" strokeWidth={1.8} />
              <span>{providers(`errors.${connect.error}`)}</span>
            </p>
            {connect.error === "stillPreparing" && (
              <Button type="button" variant="link" onClick={connect.retry} className="min-h-11 px-0">
                {providers("retry")}
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
