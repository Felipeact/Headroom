"use client"

import { type FormEvent, useId, useState, useTransition } from "react"
import { CircleAlert } from "lucide-react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"
import { type InviteError, inviteBookkeeper } from "@/app/(app)/settings/members/actions"
import { RemoveMemberDialog } from "@/components/settings/remove-member-dialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Toaster } from "@/components/ui/sonner"
import type { MemberList } from "@/lib/api/members"
import { formatDate } from "@/lib/format"

const ADDRESS = /^[^@\s]+@[^@\s]+\.[^@\s]+$/
const ADDRESS_MAX_LENGTH = 254

// A timestamp's calendar day. The API sends UTC; the day is enough for "sent" and "expires".
function day(isoDateTime: string): string {
  return formatDate(isoDateTime.slice(0, 10))
}

// Settings > Members (spec 31). No mockup: it follows settings-banks.dc.html. Owners only;
// a bookkeeper is sent to Email preferences before this renders.
export function MembersSection({ businessId, members }: { businessId: string; members: MemberList }) {
  const t = useTranslations("Settings.Members")
  const id = useId()
  const [email, setEmail] = useState("")
  const [error, setError] = useState<InviteError | null>(null)
  const [pending, startInvite] = useTransition()
  const bookkeepers = members.items.filter((member) => member.role === "bookkeeper")
  const empty = bookkeepers.length === 0 && members.invitations.length === 0

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const address = email.trim()
    if (!ADDRESS.test(address) || address.length > ADDRESS_MAX_LENGTH) {
      setError("invalid")
      return
    }
    setError(null)
    startInvite(async () => {
      const result = await inviteBookkeeper(businessId, address)
      if (result.error) {
        setError(result.error)
        return
      }
      setEmail("")
      toast(t("invited", { email: address }))
    })
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1.5">
        <h2 className="text-[22px] font-semibold">{t("title")}</h2>
        <p className="text-[15px] text-ink-2">{t("intro")}</p>
      </div>

      <form noValidate onSubmit={submit} className="flex flex-col gap-2">
        <Label htmlFor={`${id}-email`}>{t("inviteLabel")}</Label>
        <div className="flex flex-col gap-3 sm:flex-row">
          <Input
            id={`${id}-email`}
            type="email"
            autoComplete="off"
            placeholder={t("invitePlaceholder")}
            value={email}
            maxLength={ADDRESS_MAX_LENGTH}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? `${id}-error` : undefined}
            onChange={(event) => setEmail(event.target.value)}
          />
          <Button type="submit" disabled={pending} aria-busy={pending} className="shrink-0">
            {pending ? t("inviting") : t("inviteButton")}
          </Button>
        </div>
        <div role="alert">
          {error && (
            <p id={`${id}-error`} className="flex items-start gap-1.5 text-[13px] text-danger-text">
              <CircleAlert aria-hidden="true" className="mt-px size-4 shrink-0" strokeWidth={1.8} />
              <span>{t(`errors.${error}`)}</span>
            </p>
          )}
        </div>
      </form>

      <section aria-labelledby={`${id}-people`} className="flex flex-col gap-3">
        <h3 id={`${id}-people`} className="text-[17px] font-semibold">
          {t("peopleTitle")}
        </h3>
        <Card>
          <CardContent className="flex flex-col divide-y divide-line-soft">
            {members.items.map((member) => {
              const name = member.name ?? member.email ?? t("unnamed")
              return (
                <div
                  key={member.user_id}
                  data-testid="member-row"
                  className="flex min-h-11 items-center justify-between gap-4 py-3 first:pt-0 last:pb-0"
                >
                  <div className="flex min-w-0 flex-col gap-0.5">
                    <span className="truncate text-[15px] font-semibold">{name}</span>
                    <span className="truncate text-sm text-ink-2">
                      {t(`roles.${member.role}`)}
                      {member.email && member.name ? ` · ${member.email}` : ""}
                    </span>
                  </div>
                  {member.role === "bookkeeper" && (
                    <RemoveMemberDialog businessId={businessId} userId={member.user_id} name={name} />
                  )}
                </div>
              )
            })}
          </CardContent>
        </Card>
      </section>

      {members.invitations.length > 0 && (
        <section aria-labelledby={`${id}-pending`} className="flex flex-col gap-3">
          <h3 id={`${id}-pending`} className="text-[17px] font-semibold">
            {t("pendingTitle")}
          </h3>
          <Card>
            <CardContent className="flex flex-col divide-y divide-line-soft">
              {members.invitations.map((invitation) => (
                <p
                  key={invitation.id}
                  data-testid="pending-invitation"
                  className="flex min-h-11 items-center py-3 text-[15px] first:pt-0 last:pb-0"
                >
                  {t("pendingRow", {
                    sent: day(invitation.created_at),
                    expires: day(invitation.expires_at),
                  })}
                </p>
              ))}
            </CardContent>
          </Card>
        </section>
      )}

      {empty && (
        <div data-testid="members-empty" className="flex flex-col gap-1">
          <p className="text-[15px] font-semibold">{t("emptyTitle")}</p>
          <p className="text-[15px] text-ink-2">{t("emptyBody")}</p>
        </div>
      )}
      <Toaster customAriaLabel={t("notifications")} />
    </div>
  )
}
