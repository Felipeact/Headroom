import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { createTranslator, NextIntlClientProvider } from 'next-intl'
import { afterEach, beforeAll, beforeEach, expect, test, vi } from 'vitest'
import { createBusiness } from '@/app/onboarding/business/actions'
import BusinessStepPage from '@/app/onboarding/business/page'
import { BusinessForm } from '@/components/onboarding/business-form'
import { api } from '@/lib/api/client'
import messages from '@/messages/en.json'

vi.mock('@/app/onboarding/business/actions', () => ({ createBusiness: vi.fn() }))
// For the page itself (C26): signed in, and GET /v1/businesses answers no business.
vi.mock('server-only', () => ({}))
vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn() } }))
vi.mock('@/lib/api/auth', () => ({
  authHeaders: vi.fn().mockResolvedValue({ Authorization: 'Bearer tok_test' }),
}))
vi.mock('@clerk/nextjs/server', () => ({ auth: { protect: vi.fn().mockResolvedValue({}) } }))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
vi.mock('next-intl/server', () => ({
  getTranslations: async () => createTranslator({ locale: 'en', messages }),
}))
vi.mock('next/navigation', () => ({
  redirect: vi.fn(),
  useRouter: () => ({ refresh: vi.fn() }),
}))

const copy = messages.Onboarding.Business
const errors = copy.errors

// Radix Select measures and captures pointers; jsdom implements neither.
beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false
  Element.prototype.releasePointerCapture ??= () => {}
  Element.prototype.scrollIntoView ??= () => {}
})

let zone = 'America/Toronto'
const realDateTimeFormat = Intl.DateTimeFormat

beforeEach(() => {
  zone = 'America/Toronto'
  vi.spyOn(Intl, 'DateTimeFormat').mockImplementation(
    (...args: ConstructorParameters<typeof Intl.DateTimeFormat>) => {
      const format = new realDateTimeFormat(...args)
      const resolved = format.resolvedOptions()
      return Object.assign(format, { resolvedOptions: () => ({ ...resolved, timeZone: zone }) })
    },
  )
  vi.mocked(createBusiness).mockReset()
})

afterEach(() => {
  vi.restoreAllMocks()
})

function renderForm() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <BusinessForm />
    </NextIntlClientProvider>,
  )
}

async function renderPage() {
  vi.mocked(api.GET).mockResolvedValue({
    data: { items: [] },
    response: new Response('{"items":[]}', { status: 200 }),
  } as unknown as Awaited<ReturnType<typeof api.GET>>)
  const tree = await BusinessStepPage()
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {tree}
    </NextIntlClientProvider>,
  )
}

const nameField = () => screen.getByLabelText(copy.nameLabel)
const provinceField = () => screen.getByRole('combobox', { name: copy.provinceLabel })
const timeZoneField = () => screen.getByRole('combobox', { name: copy.timeZoneLabel })
const continueButton = () => screen.getByRole('button', { name: copy.continue })

function options(trigger: HTMLElement): string[] {
  fireEvent.keyDown(trigger, { key: 'Enter' })
  const names = within(screen.getByRole('listbox'))
    .getAllByRole('option')
    .map((option) => option.textContent ?? '')
  fireEvent.keyDown(screen.getByRole('listbox'), { key: 'Escape' })
  return names
}

function choose(trigger: HTMLElement, name: string) {
  fireEvent.keyDown(trigger, { key: 'Enter' })
  fireEvent.keyDown(screen.getByRole('option', { name }), { key: 'Enter' })
}

function describedBy(element: HTMLElement): string[] {
  return (element.getAttribute('aria-describedby') ?? '').split(' ').filter(Boolean)
}

test('renders the mockup', async () => {
  const { container } = await renderPage()

  const order = [
    messages.Shell.wordmark,
    'Step 2 of 5',
    copy.title,
    copy.intro,
    copy.nameLabel,
    copy.provinceLabel,
    copy.quebecHint,
    copy.timeZoneLabel,
    copy.timeZoneHint,
    copy.continue,
  ]
  const text = container.textContent ?? ''
  const positions = order.map((part) => text.indexOf(part))
  expect(positions.every((position) => position >= 0)).toBe(true)
  expect([...positions].sort((a, b) => a - b)).toEqual(positions)

  expect(screen.getByRole('heading', { level: 1, name: copy.title })).toBeDefined()
  expect(screen.getByText(copy.intro).tagName).toBe('P')

  const bar = screen.getByTestId('step-bar')
  expect(bar.getAttribute('aria-hidden')).toBe('true')
  const segments = Array.from(bar.children)
  expect(segments).toHaveLength(5)
  expect(segments.filter((segment) => segment.className.includes('bg-accent'))).toHaveLength(2)

  expect(nameField().tagName).toBe('INPUT')
  expect(provinceField()).toBeDefined()
  expect(timeZoneField()).toBeDefined()
  expect(continueButton()).toBeDefined()
})

test('province options', () => {
  renderForm()

  expect(provinceField().textContent).toBe(copy.provincePlaceholder)
  expect(options(provinceField())).toEqual([
    'Alberta',
    'British Columbia',
    'Manitoba',
    'New Brunswick',
    'Newfoundland and Labrador',
    'Northwest Territories',
    'Nova Scotia',
    'Nunavut',
    'Ontario',
    'Prince Edward Island',
    'Quebec',
    'Saskatchewan',
    'Yukon',
  ])
})

test('time zone options', () => {
  zone = 'America/Winnipeg'
  const first = renderForm()

  expect(timeZoneField().textContent).toBe('Central Time (Winnipeg)')
  expect(options(timeZoneField())).toEqual([
    "Newfoundland Time (St. John's)",
    'Atlantic Time (Halifax)',
    'Eastern Time (Toronto)',
    'Central Time (Winnipeg)',
    'Saskatchewan Time (Regina)',
    'Mountain Time (Edmonton)',
    'Pacific Time (Vancouver)',
    'Yukon Time (Whitehorse)',
  ])
  first.unmount()

  zone = 'Europe/London'
  renderForm()
  expect(timeZoneField().textContent).toBe(copy.timeZonePlaceholder)
})

test('quebec message', () => {
  renderForm()

  choose(provinceField(), 'Quebec')

  const message = screen.getByText(errors.quebec)
  const holder = message.closest('p')
  expect(holder?.className).toContain('text-danger-text')
  expect(describedBy(provinceField())).toContain(holder?.id)
  expect(createBusiness).not.toHaveBeenCalled()

  choose(provinceField(), 'Ontario')
  expect(screen.queryByText(errors.quebec)).toBeNull()
})

test.each([
  ['empty name', { name: '', province: 'Ontario' }, 'name', errors.nameRequired],
  ['no province', { name: 'Harbor Street Plumbing' }, 'province', errors.provinceRequired],
  [
    'no time zone',
    { name: 'Harbor Street Plumbing', province: 'Ontario', noZone: true },
    'time_zone',
    errors.timeZoneRequired,
  ],
  ['quebec', { name: 'Harbor Street Plumbing', province: 'Quebec' }, 'province', errors.quebec],
])('client validation: %s', (_, values, field, expected) => {
  if ('noZone' in values) zone = 'Europe/London'
  renderForm()
  fireEvent.change(nameField(), { target: { value: values.name } })
  if ('province' in values && values.province) choose(provinceField(), values.province)

  fireEvent.click(continueButton())

  expect(createBusiness).not.toHaveBeenCalled()
  const control = { name: nameField, province: provinceField, time_zone: timeZoneField }[
    field as 'name' | 'province' | 'time_zone'
  ]()
  const message = screen.getByText(expected).closest('p')
  expect(describedBy(control)).toContain(message?.id)
  expect(control.getAttribute('aria-invalid')).toBe('true')
  expect(document.activeElement).toBe(control)
})

async function fillAndSubmit() {
  fireEvent.change(nameField(), { target: { value: 'Harbor Street Plumbing' } })
  choose(provinceField(), 'Ontario')
  await act(async () => {
    fireEvent.click(continueButton())
  })
}

test('save error keeps values', async () => {
  vi.mocked(createBusiness).mockResolvedValue({ formError: true })
  renderForm()

  await fillAndSubmit()

  expect(createBusiness).toHaveBeenCalledWith({
    name: 'Harbor Street Plumbing',
    province: 'ON',
    time_zone: 'America/Toronto',
  })
  const alert = screen.getByRole('alert')
  expect(alert.textContent).toBe(errors.saveFailed)
  expect(alert.compareDocumentPosition(continueButton()) & Node.DOCUMENT_POSITION_FOLLOWING).toBe(
    Node.DOCUMENT_POSITION_FOLLOWING,
  )
  expect((nameField() as HTMLInputElement).value).toBe('Harbor Street Plumbing')
  expect(provinceField().textContent).toBe('Ontario')
  expect(timeZoneField().textContent).toBe('Eastern Time (Toronto)')
})

test('pending state', async () => {
  let finish: (value: { formError: true }) => void = () => {}
  vi.mocked(createBusiness).mockReturnValue(
    new Promise((resolve) => {
      finish = resolve
    }),
  )
  renderForm()

  await fillAndSubmit()

  expect(continueButton().getAttribute('aria-busy')).toBe('true')
  expect((continueButton() as HTMLButtonElement).disabled).toBe(true)
  await act(async () => {
    fireEvent.click(continueButton())
    fireEvent.submit(continueButton().closest('form') as HTMLFormElement)
  })
  expect(createBusiness).toHaveBeenCalledTimes(1)

  await act(async () => finish({ formError: true }))
  expect(continueButton().getAttribute('aria-busy')).toBe('false')
})
