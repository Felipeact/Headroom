import { render, screen, within } from '@testing-library/react'
import { NextIntlClientProvider, createTranslator } from 'next-intl'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import SettingsPage from '@/app/(app)/settings/page'
import BusinessSettingsPage from '@/app/(app)/settings/business/page'
import DataSettingsPage from '@/app/(app)/settings/data/page'
import MembersSettingsPage from '@/app/(app)/settings/members/page'
import { SettingsNav } from '@/components/settings/settings-nav'
import messages from '@/messages/en.json'

vi.mock('@clerk/nextjs/server', () => ({ auth: { protect: vi.fn().mockResolvedValue({}) } }))
vi.mock('next-intl/server', () => ({
  getTranslations: async () => createTranslator({ locale: 'en', messages }),
}))
const navigation = vi.hoisted(() => ({
  pathname: '/settings/banks',
  redirect: vi.fn((url: string) => {
    throw new Error(`NEXT_REDIRECT ${url}`)
  }),
}))
vi.mock('next/navigation', () => ({
  redirect: navigation.redirect,
  usePathname: () => navigation.pathname,
}))

function inIntl(tree: React.ReactNode) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {tree}
    </NextIntlClientProvider>,
  )
}

beforeEach(() => {
  navigation.redirect.mockClear()
  navigation.pathname = '/settings/banks'
})

describe('settings', () => {
  test('C4 settings redirects to banks', async () => {
    await expect(SettingsPage()).rejects.toThrow('NEXT_REDIRECT')

    expect(navigation.redirect).toHaveBeenCalledWith('/settings/banks')
  })

  test('C5 section navigation', () => {
    inIntl(<SettingsNav />)

    const nav = screen.getByRole('navigation', { name: 'Settings' })
    const links = within(nav).getAllByRole('link')
    expect(links.map((link) => [link.textContent, link.getAttribute('href')])).toEqual([
      ['Business', '/settings/business'],
      ['Bank connections', '/settings/banks'],
      ['Members', '/settings/members'],
      ['Email preferences', '/settings/email'],
      ['Your data', '/settings/data'],
    ])
    expect(links.filter((link) => link.getAttribute('aria-current') === 'page')).toEqual([
      within(nav).getByRole('link', { name: 'Bank connections' }),
    ])
  })

  // Email preferences stopped being a placeholder in spec 28 (its own tests).
  test.each([
    ['Business', BusinessSettingsPage],
    ['Members', MembersSettingsPage],
    ['Your data', DataSettingsPage],
  ])('C6 placeholder sections: %s', async (title, Page) => {
    inIntl(await Page())

    expect(screen.getByRole('heading', { name: title })).toBeTruthy()
    expect(screen.getByText(messages.Pages.comingSoon)).toBeTruthy()
  })
})
