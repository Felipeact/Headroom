// Boundary proof for spec 06 C33 and spec 07 C39: a production build must answer 404 for the
// development-only pages and 200 for the shell pages. Run after `npm run build`.
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const port = 3100
const base = `http://localhost:${port}`
const nextBin = fileURLToPath(new URL('../node_modules/next/dist/bin/next', import.meta.url))
const server = spawn(process.execPath, [nextBin, 'start', '-p', String(port)], {
  cwd: fileURLToPath(new URL('..', import.meta.url)),
  stdio: 'ignore',
})

async function status(path) {
  const response = await fetch(base + path, { redirect: 'manual' })
  return response.status
}

async function waitForServer() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      return await status('/')
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 500))
    }
  }
  throw new Error(`next start did not answer on ${base} within 30s`)
}

let failed = false
try {
  await waitForServer()
  const expected = {
    '/': 200,
    '/expected-payments': 200,
    '/alerts': 200,
    '/settings': 200,
    '/dev/components': 404,
    '/dev/sentry-check': 404,
  }
  const lines = []
  for (const [path, want] of Object.entries(expected)) {
    const got = await status(path)
    lines.push(`GET ${path} -> ${got}`)
    if (got !== want) failed = true
  }
  console.log(lines.join('; '))
} catch (error) {
  console.error(error)
  failed = true
} finally {
  server.kill()
}
process.exit(failed ? 1 : 0)
