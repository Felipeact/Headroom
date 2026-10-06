import { auth } from "@clerk/nextjs/server"
import { ExpectedPayments } from "@/components/expected-payments/expected-payments"
import { ExpectedPaymentsError } from "@/components/expected-payments/expected-payments-error"
import { loadConnections } from "@/lib/api/bank"
import { loadBusinesses } from "@/lib/api/businesses"
import { loadExpectedPayments } from "@/lib/api/expected-payments"

// Expected payments (spec 20), from design/mockups/expected-payments.dc.html.
export default async function ExpectedPaymentsPage() {
  await auth.protect()
  const businesses = await loadBusinesses()
  const business = businesses?.[0]
  if (!business) return <ExpectedPaymentsError />
  const [payments, connections] = await Promise.all([
    loadExpectedPayments(business.id),
    loadConnections(business.id),
  ])
  if (!payments || !connections) return <ExpectedPaymentsError />

  // Only accounts counted as cash can hold an expected payment (AC 3).
  const accounts = connections
    .flatMap((connection) => connection.accounts)
    .filter((account) => account.included)
    .map(({ id, name, primary }) => ({ id, name, primary }))

  return <ExpectedPayments businessId={business.id} payments={payments} accounts={accounts} />
}
