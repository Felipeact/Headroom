import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { fireEvent, render, screen } from '@testing-library/react'
import * as Sentry from '@sentry/nextjs'
import { NextIntlClientProvider } from 'next-intl'
import type { ReactNode } from 'react'
import { beforeEach, expect, test, vi } from 'vitest'
import messages from '@/messages/en.json'
import ErrorState from './error'
import Loading from './loading'

vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn() }))

beforeEach(() => {
  vi.mocked(Sentry.captureException).mockClear()
})

function withMessages(ui: ReactNode) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {ui}
    </NextIntlClientProvider>,
  )
}

function messageValues(node: unknown): string[] {
  if (typeof node === 'string') return [node]
  return Object.values(node as Record<string, unknown>).flatMap(messageValues)
}

function renderedStrings(container: HTMLElement): string[] {
  const found: string[] = []
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT)
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = node.textContent?.trim()
    if (text) found.push(text)
  }
  for (const el of container.querySelectorAll('[aria-label]')) {
    found.push(el.getAttribute('aria-label') ?? '')
  }
  return found
}

test('C23 loading state', () => {
  const { container } = withMessages(<Loading />)
  const busy = container.querySelector('[aria-busy="true"]')
  expect(busy).not.toBeNull()
  expect(busy!.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThanOrEqual(1)
})

test('C24 error state', () => {
  expect(existsSync(join(__dirname, 'layout.tsx'))).toBe(true)
  expect(existsSync(join(__dirname, 'error.tsx'))).toBe(true)
  const { container } = withMessages(<ErrorState error={new Error('boom')} retry={() => {}} />)
  expect(screen.getByText("We couldn't load this page")).toBeDefined()
  expect(container.querySelectorAll('svg[aria-hidden="true"]')).toHaveLength(1)
  expect(screen.getByRole('button', { name: 'Try again' })).toBeDefined()
})

test('C25 try again resets', () => {
  const retry = vi.fn()
  withMessages(<ErrorState error={new Error('boom')} retry={retry} />)
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(retry).toHaveBeenCalledTimes(1)
})

test('C26 reports to sentry', () => {
  const error = new Error('boom')
  withMessages(<ErrorState error={error} retry={() => {}} />)
  expect(Sentry.captureException).toHaveBeenCalledTimes(1)
  expect(Sentry.captureException).toHaveBeenCalledWith(error)
})

test('C20 text from messages', () => {
  const values = new Set(messageValues(messages))
  const loading = withMessages(<Loading />)
  const error = withMessages(<ErrorState error={new Error('boom')} retry={() => {}} />)
  const strings = [...renderedStrings(loading.container), ...renderedStrings(error.container)]
  expect(strings.length).toBeGreaterThan(0)
  for (const text of strings) {
    expect(values, `"${text}"`).toContain(text)
  }
})
