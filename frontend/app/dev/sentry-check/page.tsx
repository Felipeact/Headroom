import { auth } from "@clerk/nextjs/server"
import { notFound } from "next/navigation"
import { SentryCheckButtons } from "./sentry-check-buttons"

// Development-only page that raises deliberate errors so a reviewer can see them in Sentry
// (spec 07). `?run=<nonce>` tags the messages so one run's events can be found again. The
// copy is for developers, so it is not in messages/en.json.
export default async function SentryCheckPage({ searchParams }: PageProps<"/dev/sentry-check">) {
  if (process.env.NODE_ENV === "production") notFound()
  await auth.protect()
  const { run } = await searchParams
  const runId = typeof run === "string" ? run : ""

  return (
    <main className="mx-auto flex w-full max-w-[1440px] flex-col gap-6 px-4 py-8 lg:px-12 lg:py-12">
      <h1 className="font-heading text-[30px] font-semibold tracking-[-0.02em] sm:text-[40px]">
        Sentry check
      </h1>
      <p className="text-sm text-ink-2">
        Each button raises an error that Sentry should report to the headroom-web project.
      </p>
      <SentryCheckButtons runId={runId} />
    </main>
  )
}
