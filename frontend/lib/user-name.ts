import "server-only"
import { currentUser } from "@clerk/nextjs/server"

/** The signed-in user's name for the shell: full name, then primary email, then username. */
export async function getUserName(): Promise<string | null> {
  const user = await currentUser()
  if (!user) return null
  return user.fullName || user.primaryEmailAddress?.emailAddress || user.username || null
}
