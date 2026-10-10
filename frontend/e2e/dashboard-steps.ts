import { execFileSync } from 'node:child_process'
import type { Page } from '@playwright/test'

export const API = 'http://localhost:8100'

/** Load the Harbor Street sample (spec 18) for this Clerk user, through the real services. */
export function loadSample(clerkUserId: string) {
  execFileSync('uv', ['run', 'python', '-m', 'app.fixtures.load', 'harbor_street', '--clerk-user-id', clerkUserId], {
    cwd: '../services/core',
    stdio: ['ignore', 'ignore', 'inherit'],
  })
}

/** The signed-in user's Clerk session token, read once Clerk has loaded on the page. */
async function sessionToken(page: Page): Promise<string> {
  await page.waitForFunction(() => Boolean((window as unknown as { Clerk?: { session?: unknown } }).Clerk?.session))
  return page.evaluate(async () => {
    const clerkJs = (window as unknown as { Clerk: { session: { getToken: () => Promise<string> } } }).Clerk
    return clerkJs.session.getToken()
  })
}

/** Call the API as the signed-in user, from the test (the browser never calls the API). */
export async function callApi(page: Page, method: 'GET' | 'PUT', path: (businessId: string) => string, data?: unknown) {
  const headers = { Authorization: `Bearer ${await sessionToken(page)}` }
  const businesses = await (await page.request.get(`${API}/v1/businesses`, { headers })).json()
  const url = `${API}${path(businesses.items[0].id)}`
  const response = method === 'GET' ? await page.request.get(url, { headers }) : await page.request.put(url, { headers, data })
  if (!response.ok()) throw new Error(`${method} ${url} returned ${response.status()}`)
  return response.json()
}

export type DashboardJson = {
  projected_low: { week_starts_on: string; balance_cents: number } | null
  alerts: { id: string }[]
  upcoming: { id: string; description: string | null }[]
  forecast: { weeks: unknown[] } | null
}

export const getDashboard = (page: Page): Promise<DashboardJson> =>
  callApi(page, 'GET', (id) => `/v1/businesses/${id}/dashboard`)
