import { beforeEach, describe, expect, test, vi } from 'vitest'
import { createBusiness } from '@/app/onboarding/business/actions'
import { api } from '@/lib/api/client'

vi.mock('server-only', () => ({}))
vi.mock('@/lib/api/client', () => ({ api: { POST: vi.fn() } }))
vi.mock('@/lib/api/auth', () => ({
  authHeaders: vi.fn().mockResolvedValue({ Authorization: 'Bearer tok_test' }),
}))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
const redirect = vi.hoisted(() =>
  vi.fn((url: string) => {
    throw new Error(`NEXT_REDIRECT ${url}`)
  }),
)
vi.mock('next/navigation', () => ({ redirect }))

type PostResult = Awaited<ReturnType<typeof api.POST>>

const INPUT = {
  name: 'Harbor Street Plumbing',
  province: 'ON',
  time_zone: 'America/Toronto',
} as const

function answers(status: number, error?: unknown) {
  vi.mocked(api.POST).mockResolvedValue({
    data: status === 201 ? { id: 'b1' } : undefined,
    error,
    response: new Response(null, { status }),
  } as unknown as PostResult)
}

beforeEach(() => {
  vi.mocked(api.POST).mockReset()
  redirect.mockClear()
})

describe('create business action', () => {
  test('201 redirects to onboarding step 3, with the body and the token', async () => {
    answers(201)

    await expect(createBusiness(INPUT)).rejects.toThrow('NEXT_REDIRECT')

    // Spec 12 AC 24: step 2 now leads to step 3 (spec 11 sent it to the dashboard).
    expect(redirect).toHaveBeenCalledWith('/onboarding/bank')
    expect(api.POST).toHaveBeenCalledWith('/v1/businesses', {
      body: { name: 'Harbor Street Plumbing', province: 'ON', time_zone: 'America/Toronto' },
      headers: { Authorization: 'Bearer tok_test' },
    })
  })

  test('409 redirects to the dashboard', async () => {
    answers(409, { status: 409, detail: 'You already own a business.' })

    await expect(createBusiness(INPUT)).rejects.toThrow('NEXT_REDIRECT')

    expect(redirect).toHaveBeenCalledWith('/')
  })

  test('422 province_not_available returns the quebec field error', async () => {
    answers(422, {
      status: 422,
      detail: 'The request did not pass validation.',
      errors: [
        {
          loc: ['body', 'province'],
          msg: "Headroom isn't available in Quebec yet.",
          type: 'province_not_available',
        },
      ],
    })

    await expect(createBusiness({ ...INPUT, province: 'QC' })).resolves.toEqual({
      fieldErrors: { province: 'quebec' },
    })
    expect(redirect).not.toHaveBeenCalled()
  })

  test('500 returns the form error', async () => {
    answers(500, { status: 500 })

    await expect(createBusiness(INPUT)).resolves.toEqual({ formError: true })
    expect(redirect).not.toHaveBeenCalled()
  })

  test('a rejected call returns the form error', async () => {
    vi.mocked(api.POST).mockRejectedValue(new TypeError('fetch failed'))

    await expect(createBusiness(INPUT)).resolves.toEqual({ formError: true })
    expect(redirect).not.toHaveBeenCalled()
  })
})
