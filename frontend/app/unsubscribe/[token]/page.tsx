import { getTranslations } from "next-intl/server"
import { UnsubscribeForm } from "@/components/unsubscribe/unsubscribe-form"

// The footer's "Unsubscribe" link (spec 28, door 4). Public: no auth.protect(), because the
// link must work signed out; the token is the credential. Opening the page changes nothing
// (link scanners open every link), and only the button unsubscribes. Laid out like
// onboarding: one column, at most 480px wide, centred on desktop.
export default async function UnsubscribePage({ params }: PageProps<"/unsubscribe/[token]">) {
  const { token } = await params
  const t = await getTranslations("Shell")

  return (
    <main id="main" className="mx-auto flex w-full max-w-[480px] flex-1 flex-col gap-6 px-5 pt-6 pb-7">
      <span className="font-heading text-[22px] font-semibold tracking-[-0.01em]">{t("wordmark")}</span>
      <UnsubscribeForm token={token} />
    </main>
  )
}
