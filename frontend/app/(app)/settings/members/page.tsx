import { auth } from "@clerk/nextjs/server"
import { SettingsPlaceholder } from "@/components/settings/settings-placeholder"

export default async function MembersSettingsPage() {
  await auth.protect()
  return <SettingsPlaceholder section="members" />
}
