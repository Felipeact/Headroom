import { AppHeader } from "@/components/shell/app-header"
import { SkipLink } from "@/components/shell/skip-link"

export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <div
      data-testid="shell"
      className="mx-auto flex w-full max-w-[1440px] flex-1 flex-col gap-4 px-4 pt-4 pb-8 lg:gap-7 lg:px-12 lg:pt-7 lg:pb-12"
    >
      <SkipLink />
      <AppHeader />
      <main id="main" tabIndex={-1} className="flex flex-col gap-6 focus:outline-none">
        {children}
      </main>
    </div>
  )
}
