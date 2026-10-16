import { execFileSync } from 'node:child_process'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { expect, test } from 'vitest'
import { sentryOptions } from '@/lib/sentry-options'

const ROOT = join(__dirname, '..')
const INIT_FILES = ['instrumentation-client.ts', 'sentry.server.config.ts', 'sentry.edge.config.ts']
const SKIP_DIRS = new Set(['node_modules', '.next', 'test-results', 'playwright-report'])
const DSN = /https:\/\/[0-9a-f]+@[\w.-]*ingest[\w.-]*sentry\.io\/\d+/

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return SKIP_DIRS.has(name) ? [] : walk(path)
    return [path]
  })
}

test('C40 no example routes', () => {
  const paths = walk(join(ROOT, 'app')).map((path) => relative(ROOT, path))
  expect(paths.filter((path) => /sentry-example-(page|api)/.test(path))).toEqual([])
})

test('C41 init options', () => {
  for (const file of INIT_FILES) {
    const source = readFileSync(join(ROOT, file), 'utf8')
    expect(source, file).toContain('dsn: process.env.NEXT_PUBLIC_SENTRY_DSN')
    expect(source, file).toContain('...sentryOptions')
    for (const forbidden of ['tracesSampleRate', 'tracesSampler', 'replayIntegration', 'enableLogs: true']) {
      expect(source, `${file} contains ${forbidden}`).not.toContain(forbidden)
    }
  }
  expect(sentryOptions.dataCollection).toEqual({
    userInfo: false,
    cookies: false,
    httpHeaders: false,
    httpBodies: [],
    urlQueryParams: false,
    stackFrameVariables: false,
  })
})

// Source is every file git tracks or would track. Ignored files such as .env.local are where the
// DSN is meant to live, and node_modules and .next are ignored too.
function sourceFiles(): string[] {
  return execFileSync('git', ['ls-files', '--cached', '--others', '--exclude-standard'], {
    cwd: ROOT,
    encoding: 'utf8',
  })
    .split('\n')
    .filter(Boolean)
}

test('C41 no dsn in source', () => {
  // Split so this file does not contain a match itself.
  expect(DSN.test('https://0123abcd@o42.' + 'ingest.us.sentry.io/4507')).toBe(true)
  const files = sourceFiles()
  expect(files).toContain('instrumentation-client.ts')
  const leaks = files
    .filter((path) => !/\.(png|ico|jpe?g|woff2?)$/.test(path))
    .filter((path) => DSN.test(readFileSync(join(ROOT, path), 'utf8')))
  expect(leaks).toEqual([])
})
