import { auth } from "@clerk/nextjs/server"
import { EmailPreferencesForm } from "@/components/settings/email-preferences-form"
import { loadEmailPreferences } from "@/lib/api/email-preferences"

// Settings > Email preferences (spec 28). No mockup: it follows settings-banks.dc.html.
export default async function EmailSettingsPage() {
  await auth.protect()
  const preferences = await loadEmailPreferences()
  // The (app) error state: "We couldn't load this page" with "Try again".
  if (!preferences) throw new Error("Email preferences could not be loaded")

  return <EmailPreferencesForm initial={preferences} />
}
