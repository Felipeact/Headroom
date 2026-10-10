import { execFileSync } from 'node:child_process'

// Spec 28: read a user's unsubscribe token and email choices through the real services, in
// the same local database the e2e API (port 8100) uses.
const SCRIPT = `
import json, sys
from app.db import get_sessionmaker
from app.modules.accounts import service as accounts
from app.modules.notifications import service as notifications

with get_sessionmaker()() as session:
    user = accounts.get_or_create_user(session, sys.argv[1])
    prefs = notifications.get_preferences(session, user.id)
    token = notifications.unsubscribe_token(session, user.id)
print(json.dumps({"token": token, "alerts": prefs.alerts, "weekly_digest": prefs.weekly_digest}))
`

/** The user's unsubscribe token (issued on first need) and current email choices. */
export function emailState(clerkUserId: string): { token: string; alerts: boolean; weekly_digest: boolean } {
  const out = execFileSync('uv', ['run', 'python', '-c', SCRIPT, clerkUserId], {
    cwd: '../services/core',
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'inherit'],
  })
  return JSON.parse(out.trim().split('\n').at(-1) ?? '{}')
}
