import { auth } from "@clerk/nextjs/server"
import { getTranslations } from "next-intl/server"
import { SettingsNav } from "@/components/settings/settings-nav"

// Settings, from design/mockups/settings-banks.dc.html (spec 17): the section list beside the
// section, or above it on a phone.
export default async function SettingsLayout({ children }: LayoutProps<"/settings">) {
  await auth.protect()
  const t = await getTranslations("Settings")

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-heading text-[30px] font-semibold tracking-[-0.02em] sm:text-[40px]">{t("title")}</h1>
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:gap-8">
        <SettingsNav />
        <div className="flex min-w-0 flex-1 flex-col gap-5">{children}</div>
      </div>
    </div>
  )
}
