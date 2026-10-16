import { createTranslator, type useTranslations } from 'next-intl'
import { expect, test } from 'vitest'
import messages from '@/messages/en.json'

type NavTranslator = ReturnType<typeof useTranslations<'Nav'>>

// C22's type-level half: useTranslations knows the keys only through AppConfig (global.ts).
// `npm run typecheck` fails on an unused @ts-expect-error, so this compiles only while unknown
// keys are rejected. Never called; it exists for the type checker.
export function unknownKeyIsRejected(t: NavTranslator) {
  // @ts-expect-error noSuchKey is not in messages/en.json
  return t('noSuchKey')
}

test('C22 unknown key is a type error', () => {
  const t = createTranslator({ locale: 'en', messages, namespace: 'Nav' })
  expect(t('dashboard')).toBe('Dashboard')
  // @ts-expect-error noSuchKey is not in messages/en.json
  expect(t('noSuchKey')).toBe('Nav.noSuchKey')
})
