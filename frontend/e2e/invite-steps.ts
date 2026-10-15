import { execFileSync } from 'node:child_process'

// Spec 31: make an invitation through the real service, in the same local database the e2e API
// uses, and print its token (only a hash is stored, so the token cannot be read back later).
const SCRIPT = `
import sys
from sqlalchemy import text
from app.db import get_sessionmaker
from app.modules.accounts import service as accounts

clerk_user_id, address, expired = sys.argv[1], sys.argv[2], sys.argv[3] == "expired"
tokens = []
with get_sessionmaker()() as session:
    user = accounts.get_or_create_user(session, clerk_user_id)
    business = accounts.list_businesses(session, user.id)[0]
    accounts.invite(
        session,
        business_id=business.id,
        inviter_id=user.id,
        address=address,
        send=lambda to, name, inviter, token: tokens.append(token),
    )
    if expired:
        session.execute(
            text("UPDATE invitations SET expires_at = now() - interval '1 second' WHERE business_id = :b"),
            {"b": business.id},
        )
        session.commit()
print(tokens[0])
`

/** Invite the address to the business the Clerk user owns; returns the link's token. */
export function createInvitation(ownerClerkUserId: string, address: string, state: 'valid' | 'expired' = 'valid'): string {
  const out = execFileSync('uv', ['run', 'python', '-c', SCRIPT, ownerClerkUserId, address, state], {
    cwd: '../services/core',
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'inherit'],
  })
  return out.trim().split('\n').at(-1) ?? ''
}
