import { auth } from "@clerk/nextjs/server"
import { SettingsPlaceholder } from "@/components/settings/settings-placeholder"

export default async function EmailSettingsPage() {
  await auth.protect()
  return <SettingsPlaceholder section="email" />
}
