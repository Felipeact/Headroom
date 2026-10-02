import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, test } from 'vitest'

// Vitest runs from frontend/ (its config root); jsdom gives import.meta.url an http scheme.
const frontend = process.cwd()
const globalsCss = readFileSync(path.join(frontend, 'app/globals.css'), 'utf8')

// DESIGN.md's 22 colour tokens plus the two spec 06 added (door 6).
const TOKENS: Record<string, string> = {
  bg: '#F5F3EE',
  surface: '#FFFFFF',
  'surface-muted': '#F1EEE7',
  'surface-active': '#E9E5DC',
  border: '#E2DDD3',
  'border-input': '#D6D0C4',
  ink: '#16202B',
  'ink-2': '#454F5C',
  'ink-3': '#5A6370',
  accent: '#1D4E89',
  'accent-hover': '#133A68',
  positive: '#1E6B45',
  'positive-bg': '#EAF4EE',
  'warning-bg': '#FFF4E2',
  'warning-border': '#F0D3A4',
  'warning-text': '#7A4300',
  'warning-strong': '#4F2C00',
  'warning-line': '#B26B00',
  'danger-bg': '#FCEDEB',
  'danger-border': '#EFC7C2',
  'danger-text': '#8E1B1B',
  'danger-strong': '#5E1111',
  'line-soft': '#ECE8E0',
  'line-strong': '#C9C2B5',
}

function block(css: string, opener: string): string {
  const start = css.indexOf(opener)
  if (start === -1) return ''
  const end = css.indexOf('\n}', start)
  return css.slice(start, end)
}

const HEX = /#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![\w-])/
const COLOUR_FUNCTION = /\b(?:rgba?|hsl|oklch)\(/

function findColourLiterals(text: string): string[] {
  return text
    .split('\n')
    .filter((line) => HEX.test(line) || COLOUR_FUNCTION.test(line))
}

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name)
    if (statSync(full).isDirectory()) return sourceFiles(full)
    return /\.(tsx?|css|m?js)$/.test(name) ? [full] : []
  })
}

describe('C1 globals.css :root', () => {
  const root = block(globalsCss, ':root {')
  test.each(Object.entries(TOKENS))('root defines token --%s as %s', (name, hex) => {
    expect(root).toMatch(new RegExp(`--${name}:\\s*${hex};`, 'i'))
  })
  test('root defines token count is 24', () => {
    expect(Object.keys(TOKENS)).toHaveLength(24)
  })
})

describe('C2 globals.css @theme inline', () => {
  const theme = block(globalsCss, '@theme inline {')
  test.each(Object.keys(TOKENS))('theme exposes token --color-%s', (name) => {
    expect(theme).toMatch(new RegExp(`--color-${name}:\\s*var\\(--${name}\\);`))
  })
})

test('C3 no starter palette: no oklch( and no .dark block', () => {
  expect(globalsCss).not.toContain('oklch(')
  expect(globalsCss).not.toMatch(/\.dark\s*\{/)
})

test('C7 no geist in app/layout.tsx', () => {
  const layout = readFileSync(path.join(frontend, 'app/layout.tsx'), 'utf8')
  expect(layout).not.toMatch(/geist/i)
})

const COMPONENTS = [
  'button',
  'card',
  'input',
  'label',
  'select',
  'switch',
  'radio-group',
  'toggle-group',
  'dialog',
  'badge',
  'skeleton',
  'sonner',
]

test.each(COMPONENTS)('C9 component file exists: components/ui/%s.tsx', (name) => {
  expect(existsSync(path.join(frontend, 'components/ui', `${name}.tsx`))).toBe(true)
})

describe('C23 colour literals', () => {
  const files = [
    ...sourceFiles(path.join(frontend, 'components')),
    ...sourceFiles(path.join(frontend, 'app')),
  ].filter((file) => path.relative(frontend, file) !== path.join('app', 'globals.css'))

  test('no colour literals in components/ or app/ outside globals.css', () => {
    expect(files.length).toBeGreaterThan(0)
    const offenders = files.flatMap((file) =>
      findColourLiterals(readFileSync(file, 'utf8')).map(
        (line) => `${path.relative(frontend, file)}: ${line.trim()}`,
      ),
    )
    expect(offenders).toEqual([])
  })

  test.each([
    ['hex', 'className="bg-[#1D4E89]"'],
    ['rgb(', 'style={{ color: "rgb(1, 2, 3)" }}'],
    ['rgba(', 'boxShadow: "0 1px 2px rgba(22, 32, 43, 0.14)"'],
    ['hsl(', 'color: hsl(210 50% 40%)'],
    ['oklch(', 'background: oklch(0.5 0.1 250)'],
  ])('guard detects %s', (_kind, sample) => {
    expect(findColourLiterals(sample)).toEqual([sample])
  })

  test('guard ignores a plain anchor and an id', () => {
    expect(findColourLiterals('<a href="#">Manage</a> <div id="c-colors">')).toEqual([])
  })
})
