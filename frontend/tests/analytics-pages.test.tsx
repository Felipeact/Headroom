import { beforeEach, describe, expect, test, vi } from 'vitest'
import AlertPage from '@/app/(app)/alerts/[alertId]/page'
import { DashboardContent } from '@/components/dashboard/dashboard-content'
import { capture } from '@/lib/analytics'
import { loadAlert } from '@/lib/api/alerts'
import { loadBusinesses } from '@/lib/api/businesses'
import { loadDashboard } from '@/lib/api/dashboard'

// Spec 32 C12, C13: the two pages that report a view. The views themselves are rendered elsewhere.
vi.mock('server-only', () => ({}))
vi.mock('@/lib/analytics', () => ({ capture: vi.fn() }))
vi.mock('@clerk/nextjs/server', () => ({ auth: { protect: vi.fn().mockResolvedValue({}) } }))
vi.mock('@/lib/api/alerts', () => ({ loadAlert: vi.fn() }))
vi.mock('@/lib/api/businesses', () => ({ loadBusinesses: vi.fn() }))
vi.mock('@/lib/api/dashboard', () => ({ loadDashboard: vi.fn() }))
vi.mock('@/lib/api/bank', () => ({ createUpdateLinkToken: vi.fn() }))
vi.mock('@/components/dashboard/dashboard-view', () => ({ DashboardView: () => null }))
vi.mock('@/components/dashboard/dashboard-error', () => ({ DashboardError: () => null }))
vi.mock('@/components/alert-page/alert-view', () => ({ AlertView: () => null }))
vi.mock('next/navigation', () => ({
  notFound: vi.fn(() => {
    throw new Error('NEXT_NOT_FOUND')
  }),
}))

const business = (role: 'owner' | 'bookkeeper') =>
  [{ id: 'biz-1', name: 'Harbor Street Plumbing', time_zone: 'America/Toronto', role }] as Awaited<
    ReturnType<typeof loadBusinesses>
  >
const DASHBOARD = { accounts: [], connections: [] } as unknown as Awaited<ReturnType<typeof loadDashboard>>

beforeEach(() => {
  vi.mocked(capture).mockReset().mockResolvedValue(undefined)
  vi.mocked(loadBusinesses).mockReset()
  vi.mocked(loadDashboard).mockReset().mockResolvedValue(DASHBOARD)
  vi.mocked(loadAlert).mockReset()
})

describe('dashboard viewed', () => {
  test.each(['owner', 'bookkeeper'] as const)('sends the business and the %s role', async (role) => {
    vi.mocked(loadBusinesses).mockResolvedValue(business(role))
    await DashboardContent()
    expect(capture).toHaveBeenCalledExactlyOnceWith('dashboard_viewed', { business_id: 'biz-1', role })
  })

  test('sends nothing without a business, or when the dashboard fails to load', async () => {
    vi.mocked(loadBusinesses).mockResolvedValue(null)
    await DashboardContent()
    vi.mocked(loadBusinesses).mockResolvedValue(business('owner'))
    vi.mocked(loadDashboard).mockResolvedValue(null)
    await DashboardContent()
    expect(capture).not.toHaveBeenCalled()
  })
})

describe('alert opened', () => {
  const params = Promise.resolve({ alertId: 'alert-1' })

  test('a found alert sends the business, the alert and the role', async () => {
    vi.mocked(loadBusinesses).mockResolvedValue(business('bookkeeper'))
    vi.mocked(loadAlert).mockResolvedValue({ id: 'alert-1' } as Awaited<ReturnType<typeof loadAlert>>)
    await AlertPage({ params } as never)
    expect(capture).toHaveBeenCalledExactlyOnceWith('alert_opened', {
      business_id: 'biz-1',
      alert_id: 'alert-1',
      role: 'bookkeeper',
    })
  })

  test('an unknown alert sends nothing and is not found', async () => {
    vi.mocked(loadBusinesses).mockResolvedValue(business('owner'))
    vi.mocked(loadAlert).mockResolvedValue('not_found')
    await expect(AlertPage({ params } as never)).rejects.toThrow('NEXT_NOT_FOUND')
    expect(capture).not.toHaveBeenCalled()
  })
})
