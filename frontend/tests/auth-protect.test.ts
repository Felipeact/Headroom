// @vitest-environment node
import { readFileSync, readdirSync } from 'node:fs'
import { join, relative, sep } from 'node:path'
import { expect, test } from 'vitest'

const APP = join(__dirname, '..', 'app')

function routeFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) return routeFiles(path)
    return /^(page|layout)\.tsx$/.test(entry.name) ? [path] : []
  })
}

test('every page protected', () => {
  const files = routeFiles(APP)
    .map((file) => relative(APP, file).split(sep).join('/'))
    .filter(
      (file) => file !== 'layout.tsx' && !file.startsWith('sign-in/') && !file.startsWith('sign-up/'),
    )

  expect(files.length).toBeGreaterThanOrEqual(8)
  const unprotected = files.filter(
    (file) => !readFileSync(join(APP, file), 'utf8').includes('await auth.protect()'),
  )
  expect(unprotected).toEqual([])

  const proxy = readFileSync(join(__dirname, '..', 'proxy.ts'), 'utf8')
  expect(proxy).not.toMatch(/createRouteMatcher/)
})
