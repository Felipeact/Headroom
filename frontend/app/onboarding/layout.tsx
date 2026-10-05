import { auth } from "@clerk/nextjs/server"

// Onboarding is designed for phones; on desktop the same column is centred, at most 480px
// wide (DESIGN.md). No app shell: the user has no business yet.
export default async function OnboardingLayout({ children }: LayoutProps<"/onboarding">) {
  await auth.protect()

  return (
    <main
      id="main"
      className="mx-auto flex w-full max-w-[480px] flex-1 flex-col gap-6 px-5 pt-4 pb-7"
    >
      {children}
    </main>
  )
}
