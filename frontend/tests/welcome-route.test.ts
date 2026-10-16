// @vitest-environment node
import { beforeEach, describe, expect, test, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { GET } from '@/app/welcome/route'
import { capture } from '@/lib/analytics'

// Spec 32 C6: where Clerk sends a new user.
vi.mock('server-only', () => ({}))
const order: string[] = []
const protect = vi.hoisted(() => vi.fn())
vi.mock('@clerk/nextjs/server', () => ({ auth: { protect } }))
vi.mock('@/lib/analytics', () => ({ capture: vi.fn() }))
vi.mock('@clerk/nextjs', () => ({ SignUp: () => null }))

const get = (query = '', origin = 'https://app.example.test') => GET(new NextRequest(`${origin}/welcome${query}`))

beforeEach(() => {
  order.length = 0
  protect.mockReset().mockImplementation(async () => void order.push('protect'))
  vi.mocked(capture)
    .mockReset()
    .mockImplementation(async () => void order.push('capture'))
})

describe('GET /welcome', () => {
  test('protects the route, records the sign-up, and redirects to / with 307', async () => {
    const response = await get()
    expect(order).toEqual(['protect', 'capture'])
    expect(capture).toHaveBeenCalledWith('sign_up_completed', {})
    expect(response.status).toBe(307)
    expect(response.headers.get('location')).toBe('/')
  })

  // Under `next start` request.url carries the address the server listens on, not the public
  // host, so the redirect must be a path the browser resolves against the host it used.
  test('goes on to a same-site next path and never names the host the server listens on', async () => {
    const response = await get('?next=/invite/abc', 'http://localhost:8080')
    expect(response.status).toBe(307)
    expect(response.headers.get('location')).toBe('/invite/abc')
  })

  test.each(['//evil.test', 'https://evil.test', ''])('refuses next=%s', async (next) => {
    const response = await get(`?next=${encodeURIComponent(next)}`)
    expect(response.status).toBe(307)
    expect(response.headers.get('location')).toBe('/')
  })
})

describe('sign-up page', () => {
  test.each([
    [undefined, '/welcome?next=%2F'],
    ['/invite/abc', '/welcome?next=%2Finvite%2Fabc'],
    ['https://app.example.test/invite/abc?x=1', '/welcome?next=%2Finvite%2Fabc%3Fx%3D1'],
    ['//evil.test', '/welcome?next=%2F'],
  ])('redirect_url %s goes through %s', async (redirectUrl, expected) => {
    const { default: SignUpPage } = await import('@/app/sign-up/[[...sign-up]]/page')
    const page = await SignUpPage({ searchParams: Promise.resolve({ redirect_url: redirectUrl }) } as never)
    const signUp = (page.props.children as { props: { forceRedirectUrl: string } }).props
    expect(signUp.forceRedirectUrl).toBe(expected)
  })
})
