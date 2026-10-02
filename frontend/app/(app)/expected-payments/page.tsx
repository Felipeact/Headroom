import { auth } from "@clerk/nextjs/server"
import { PlaceholderPage } from "@/components/shell/placeholder-page"

export default async function ExpectedPaymentsPage() {
  await auth.protect()
  return <PlaceholderPage titleKey="expectedPayments" />
}
