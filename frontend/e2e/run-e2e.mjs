import { spawn } from 'node:child_process'

const cwd = process.cwd()
const serverPort = Number(process.env.E2E_PORT || 41739)
const serverUrl = `http://127.0.0.1:${serverPort}`

async function isServerReady() {
  try {
    const response = await fetch(serverUrl)
    return response.ok
  } catch {
    return false
  }
}

async function waitForServer(processRef) {
  const startedAt = Date.now()
  while (Date.now() - startedAt < 120_000) {
    if (await isServerReady()) return
    if (processRef.exitCode !== null) {
      throw new Error(`Vite exited before ${serverUrl} became ready`)
    }
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
  throw new Error(`Timed out waiting for ${serverUrl}`)
}

function run(command, args, options = {}) {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      cwd,
      stdio: 'inherit',
      ...options,
    })
    child.on('exit', (code) => resolve(code ?? 1))
  })
}

async function main() {
  let vite = null

  vite = spawn(
    process.execPath,
    [
      './node_modules/vite/bin/vite.js',
      '--host', '127.0.0.1',
      '--port', String(serverPort),
      '--strictPort',
    ],
    {
      cwd,
      stdio: ['ignore', 'ignore', 'inherit'],
    },
  )
  await waitForServer(vite)

  const forwardedArgs = process.argv.slice(2)
  const hasReporter = forwardedArgs.some((arg) => arg === '--reporter' || arg.startsWith('--reporter='))
  const args = ['node_modules/@playwright/test/cli.js', 'test']
  if (!hasReporter) args.push('--reporter=line')
  args.push(...forwardedArgs)

  const exitCode = await run(process.execPath, args, {
    env: { ...process.env, E2E_BASE_URL: serverUrl },
  })

  if (vite) {
    vite.kill()
    await new Promise((resolve) => vite.once('exit', resolve))
  }

  process.exit(exitCode)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
