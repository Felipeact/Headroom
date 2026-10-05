import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import ts from 'typescript'
import { expect, test } from 'vitest'
import messages from '@/messages/en.json'

const ROOTS = ['app/onboarding', 'components/onboarding']
const TEXT_ATTRIBUTES = new Set(['placeholder', 'aria-label', 'title', 'alt'])

function files(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) return files(path)
    return /\.tsx?$/.test(entry.name) && !entry.name.includes('.test.') ? [path] : []
  })
}

type Found = { literals: string[]; keys: string[] }

function scan(path: string): Found {
  const source = ts.createSourceFile(path, readFileSync(path, 'utf8'), ts.ScriptTarget.Latest, true)
  const found: Found = { literals: [], keys: [] }
  const visit = (node: ts.Node) => {
    if (ts.isJsxText(node) && /[A-Za-z]/.test(node.text)) found.literals.push(node.text.trim())
    if (
      ts.isJsxAttribute(node) &&
      TEXT_ATTRIBUTES.has(node.name.getText(source)) &&
      node.initializer &&
      ts.isStringLiteral(node.initializer)
    ) {
      found.literals.push(node.initializer.text)
    }
    if (ts.isCallExpression(node) && node.expression.getText(source) === 't') {
      const [first] = node.arguments
      if (first && ts.isStringLiteral(first)) found.keys.push(first.text)
      // `Business.errors.${key}`: the fixed part must name an object of messages.
      if (first && ts.isTemplateExpression(first)) found.keys.push(first.head.text.replace(/\.$/, ''))
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return found
}

function resolves(key: string): boolean {
  // A key is relative to the component's namespace, or to the root for getTranslations().
  return ['', 'Onboarding.', 'States.', 'Shell.'].some((namespace) => {
    let node: unknown = messages
    for (const part of `${namespace}${key}`.split('.')) {
      if (typeof node !== 'object' || node === null || !(part in node)) return false
      node = (node as Record<string, unknown>)[part]
    }
    return true
  })
}

test('no literal copy in onboarding, and every key exists', () => {
  const all = ROOTS.flatMap(files)
  expect(all.length).toBeGreaterThanOrEqual(5)

  const found = all.map((path) => ({ path, ...scan(path) }))

  expect(found.filter((f) => f.literals.length > 0).map((f) => [f.path, f.literals])).toEqual([])
  const keys = found.flatMap((f) => f.keys)
  expect(keys.length).toBeGreaterThan(10)
  expect(keys.filter((key) => !resolves(key))).toEqual([])
})
