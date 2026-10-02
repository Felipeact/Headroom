// @vitest-environment node
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { expect, test } from 'vitest'
import { CLERK_TOKENS } from '@/lib/clerk-appearance'

test('Clerk token values match globals.css', () => {
  const css = readFileSync(join(__dirname, '..', 'app', 'globals.css'), 'utf8')
  for (const [name, value] of Object.entries(CLERK_TOKENS)) {
    const declared = css.match(new RegExp(`${name}:\\s*(#[0-9A-Fa-f]{6});`))?.[1]
    expect(declared?.toUpperCase(), name).toBe(value.toUpperCase())
  }
})
