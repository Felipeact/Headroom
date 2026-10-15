import { auth } from "@clerk/nextjs/server"
import { getTranslations } from "next-intl/server"
import { InviteCard } from "@/components/invite/invite-card"
import { loadInvitation } from "@/lib/api/members"

// A bookkeeper invitation link (spec 31, door 1). It lives outside (app): the shell sends a
// user with no business to onboarding, and a bookkeeper has none until they accept. Signed-out
// visitors go to sign-in and come back here. Laid out like onboarding: one column, at most
// 480px wide, centred on desktop.
export default async function InvitePage({ params }: PageProps<"/invite/[token]">) {
  await auth.protect()
  const { token } = await params
  const shell = await getTranslations("Shell")
  const invite = await getTranslations("Invite")
  const states = await getTranslations("States")
  const found = await loadInvitation(token)
  const unknown = found.status === "not_found"

  return (
    <main id="main" className="mx-auto flex w-full max-w-[480px] flex-1 flex-col gap-6 px-5 pt-6 pb-7">
      <span className="font-heading text-[22px] font-semibold tracking-[-0.01em]">{shell("wordmark")}</span>
      {found.status === "found" ? (
        <InviteCard token={token} invitation={found.invitation} />
      ) : (
        <div role={unknown ? undefined : "alert"} className="flex flex-col gap-3">
          <h1 className="font-heading text-[26px] font-semibold leading-tight">
            {unknown ? invite("notFoundTitle") : states("errorTitle")}
          </h1>
          <p className="text-[15px] leading-normal text-ink-2">
            {unknown ? invite("notFoundBody") : states("errorBody")}
          </p>
        </div>
      )}
    </main>
  )
}
