import { auth } from "@clerk/nextjs/server"
import * as Sentry from "@sentry/nextjs"
import { AppHeader } from "@/components/shell/app-header"
import { LayoutError } from "@/components/shell/layout-error"
import { SkipLink } from "@/components/shell/skip-link"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"
import { getUserName } from "@/lib/user-name"

// GET /v1/me on every shell render: the API verifies the session and creates the user's row
// on their first visit (spec 10).
async function loadMe(): Promise<boolean> {
  try {
    const { response } = await api.GET("/v1/me", { headers: await authHeaders() })
    if (response.ok) return true
    Sentry.captureMessage(`GET /v1/me returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return false
}

export default async function AppLayout({ children }: LayoutProps<"/">) {
  await auth.protect()
  const [userName, meLoaded] = await Promise.all([getUserName(), loadMe()])

  return (
    <div
      data-testid="shell"
      className="mx-auto flex w-full max-w-[1440px] flex-1 flex-col gap-4 px-4 pt-4 pb-8 lg:gap-7 lg:px-12 lg:pt-7 lg:pb-12"
    >
      <SkipLink />
      <AppHeader userName={userName ?? undefined} />
      <main id="main" tabIndex={-1} className="flex flex-col gap-6 focus:outline-none">
        {meLoaded ? children : <LayoutError />}
      </main>
    </div>
  )
}
