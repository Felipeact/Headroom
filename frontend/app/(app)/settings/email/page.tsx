import { auth } from "@clerk/nextjs/server"
import { EmailPreferencesForm } from "@/components/settings/email-preferences-form"
import { loadBusinesses } from "@/lib/api/businesses"
import { loadEmailPreferences } from "@/lib/api/email-preferences"
import { loadMembers, loadMyUserId } from "@/lib/api/members"

// Settings > Email preferences (spec 28). No mockup: it follows settings-banks.dc.html.
export default async function EmailSettingsPage() {
  await auth.protect()
  const preferences = await loadEmailPreferences()
  // The (app) error state: "We couldn't load this page" with "Try again".
  if (!preferences) throw new Error("Email preferences could not be loaded")

  // A bookkeeper chooses, per client, whether that client's alerts reach them (spec 31). Their
  // current choice is their own row among the client's members.
  const businesses = (await loadBusinesses()) ?? []
  const bookkeeping = businesses.filter((business) => business.role === "bookkeeper")
  const me = bookkeeping.length > 0 ? await loadMyUserId() : null
  const clients = await Promise.all(
    bookkeeping.map(async ({ id, name }) => {
      const members = await loadMembers(id)
      const mine = members?.items.find((member) => member.user_id === me)
      return { id, name, enabled: mine?.receive_alert_emails ?? false }
    }),
  )
  return <EmailPreferencesForm initial={preferences} clients={clients} />
}
