// C33 boundary proof: a production build must answer 404 for /dev/components.
// Run after `npm run build`. Exits 0 only when / is 200 and /dev/components is 404.
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
  const home = await waitForServer()
  const dev = await status('/dev/components')
  console.log(`GET / -> ${home}; GET /dev/components -> ${dev}`)
  failed = home !== 200 || dev !== 404
} catch (error) {
  console.error(error)
  failed = true
} finally {
  server.kill()
}
process.exit(failed ? 1 : 0)
