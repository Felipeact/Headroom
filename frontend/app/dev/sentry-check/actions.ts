"use server"

export async function throwServerError(runId: string): Promise<void> {
  throw new Error(`Headroom web Sentry check (server) ${runId}`.trim())
}
