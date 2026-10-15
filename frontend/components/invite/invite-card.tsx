"use client"

import Link from "next/link"
import { useState, useTransition } from "react"
import { useTranslations } from "next-intl"
import { type AcceptResult, acceptInvitation } from "@/app/invite/[token]/actions"
import { Button } from "@/components/ui/button"
import type { InvitationPreview } from "@/lib/api/members"

type Outcome = AcceptResult["status"]

// The messages a link can end in, as keys under Invite in messages/en.json.
const ENDINGS = {
  accepted: "accepted",
  expired: "expired",
  wrongAddress: "wrong",
  alreadyOwner: "owner",
  notFound: "notFound",
} as const satisfies Record<Exclude<Outcome, "failed">, string>

// An invitation link (spec 31, door 1). Opening it changes nothing; the button accepts. The
// API decides who may accept, by the signed-in user's email address.
export function InviteCard({ token, invitation }: { token: string; invitation: InvitationPreview }) {
  const t = useTranslations("Invite")
  const [outcome, setOutcome] = useState<Outcome | null>(null)
  const [pending, startTransition] = useTransition()
  const business = invitation.business_name

  const ending =
    outcome && outcome !== "failed"
      ? ENDINGS[outcome]
      : invitation.status === "expired"
        ? "expired"
        : invitation.status === "accepted" && outcome === null
          ? "used"
          : null

  if (ending) {
    const done = ending === "accepted" || ending === "used"
    return (
      <div className="flex flex-col gap-3">
        <h1 className="font-heading text-[26px] font-semibold leading-tight">
          {t(`${ending}Title`, { business })}
        </h1>
        <p className="text-[15px] leading-normal text-ink-2">{t(`${ending}Body`)}</p>
        {done && (
          <Button asChild className="w-full sm:w-auto">
            <Link href="/">{t("goToDashboard")}</Link>
          </Button>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-[26px] font-semibold leading-tight">{t("title", { business })}</h1>
      <p className="text-[15px] leading-normal text-ink-2">{t("body")}</p>
      <Button
        className="w-full sm:w-auto"
        disabled={pending}
        aria-busy={pending}
        onClick={() =>
          startTransition(async () => {
            setOutcome((await acceptInvitation(token)).status)
          })
        }
      >
        {pending ? t("accepting") : t("accept")}
      </Button>
      {outcome === "failed" && (
        <p role="alert" className="text-sm text-danger-text">
          {t("failed")}
        </p>
      )}
    </div>
  )
}
