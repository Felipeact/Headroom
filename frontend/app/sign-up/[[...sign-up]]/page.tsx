import { SignUp } from "@clerk/nextjs"
import { safePath } from "@/lib/safe-path"

// A new user lands on /welcome, which records the sign-up and then continues to the page they
// were headed for (Clerk's `redirect_url`), so an invited bookkeeper still reaches the invitation.
export default async function SignUpPage({ searchParams }: PageProps<"/sign-up/[[...sign-up]]">) {
  const { redirect_url } = await searchParams
  const next = safePath(typeof redirect_url === "string" ? redirect_url : null)
  return (
    <main className="flex flex-1 items-center justify-center px-4 py-8">
      <SignUp forceRedirectUrl={`/welcome?next=${encodeURIComponent(next)}`} />
    </main>
  )
}
