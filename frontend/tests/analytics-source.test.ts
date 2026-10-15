// @vitest-environment node
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { expect, test } from 'vitest'

// Spec 32 C15: PostHog stays on the server (door 3) and never identifies anyone (door 2).
const ROOT = join(__dirname, '..')

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return sources(path)
    return /\.(ts|tsx)$/.test(name) ? [path] : []
  })
}

test('PostHog is server-only and never identifies', () => {
  expect(readFileSync(join(ROOT, 'lib', 'analytics.ts'), 'utf8').startsWith('import "server-only"')).toBe(true)

  const manifest = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8'))
  expect(Object.keys({ ...manifest.dependencies, ...manifest.devDependencies })).not.toContain('posthog-js')

  const files = ['app', 'components', 'lib'].flatMap((dir) => sources(join(ROOT, dir)))
  files.push(join(ROOT, '.env.example'))
  for (const file of files) {
    const text = readFileSync(file, 'utf8')
    expect(text, file).not.toContain('NEXT_PUBLIC_POSTHOG')
    expect(text, file).not.toMatch(/\.identify\(/)
  }
})
