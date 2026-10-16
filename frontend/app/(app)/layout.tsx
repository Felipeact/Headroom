import { auth } from "@clerk/nextjs/server"
import { redirect } from "next/navigation"
import { AppHeader } from "@/components/shell/app-header"
import { LayoutError } from "@/components/shell/layout-error"
import { SkipLink } from "@/components/shell/skip-link"
import { loadBusinesses } from "@/lib/api/businesses"
import { getUserName } from "@/lib/user-name"

export default async function AppLayout({ children }: LayoutProps<"/">) {
  await auth.protect()
  // GET /v1/businesses on every shell render: a user without a business always lands on
  // onboarding step 2 (spec 11), and the first one names the header.
  const [userName, businesses] = await Promise.all([getUserName(), loadBusinesses()])
  if (businesses?.length === 0) redirect("/onboarding/business")

  return (
    <div
      data-testid="shell"
      className="mx-auto flex w-full max-w-[1440px] flex-1 flex-col gap-4 px-4 pt-4 pb-8 lg:gap-7 lg:px-12 lg:pt-7 lg:pb-12"
    >
      <SkipLink />
      <AppHeader businessName={businesses?.[0]?.name} userName={userName ?? undefined} />
      <main id="main" tabIndex={-1} className="flex flex-col gap-6 focus:outline-none">
        {businesses ? children : <LayoutError />}
      </main>
    </div>
  )
}
