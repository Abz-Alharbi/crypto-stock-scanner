import { test, expect } from '@playwright/test'

const adminUser = {
  id: 1,
  username: 'admin_user',
  email: 'admin@example.test',
  role: 'admin',
  plan: 'premium',
  is_active: true,
  created_at: '2026-07-05T00:00:00',
}

const scanResult = {
  provider_symbol: 'AAPL',
  display_symbol: 'AAPL',
  symbol: 'AAPL',
  market: 'stocks',
  price: { last: 195.12, change_pct: 1.23, volume: 1_000_000 },
  overall_signal: 'bullish',
  match_pct: 100,
  rsi: 28.4,
  patterns: ['Hammer'],
  matched_filters: ['rsi_oversold'],
  trade_setup: {
    direction: 'long',
    action: 'Buy',
    confidence: 72,
    entry_price: 195.12,
    stop_loss: 190,
    targets: {
      t1: { price: 205, rr: 1.5, label: 'Conservative' },
      t2: { price: 212, rr: 2.5, label: 'Moderate' },
      t3: { price: 220, rr: 4, label: 'Aggressive' },
    },
    risk_reward: 1.5,
    potential_gain_pct: 5,
    potential_loss_pct: 2.6,
    atr: 3.2,
    atr_pct: 1.6,
    support_levels: [],
    resistance_levels: [],
  },
}

async function mockApi(page, options = {}) {
  const watchlist = []
  const scanRequests = []
  const jobs = new Map()

  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    const json = (body, status = 200) => route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(body),
    })

    if (path === '/api/health') {
      return json({ status: 'healthy', stock_symbols: 80, crypto_symbols: 15, api_key_configured: true })
    }

    if (path === '/api/filters') {
      return json({
        filters: {
          oscillators: {
            rsi_oversold: {
              id: 'rsi_oversold',
              name: 'RSI Oversold',
              description: 'RSI below 30',
              category: 'oscillators',
              available: true,
              supported_asset_classes: ['stocks', 'crypto'],
              supported_timeframes: ['1D'],
            },
            equity_only: {
              id: 'equity_only',
              name: 'Equity Only Strategy',
              description: 'Stocks only',
              category: 'oscillators',
              available: true,
              supported_asset_classes: ['stocks'],
              supported_timeframes: ['1D'],
            },
          },
        },
        presets: {},
        timeframes: {
          '1D': { label: '1 Day', short_label: '1D', available: true },
        },
        universes: {
          us_stocks_top: { key: 'us_stocks_top', name: 'All US Top Volume', asset_class: 'stocks', count: 80, default: true },
          nasdaq_top: { key: 'nasdaq_top', name: 'NASDAQ Top Volume', asset_class: 'stocks', count: 50, default: false },
          nyse_top: { key: 'nyse_top', name: 'NYSE Top Volume', asset_class: 'stocks', count: 30, default: false },
          crypto_static: { key: 'crypto_static', name: 'Crypto Top USD Pairs', asset_class: 'crypto', count: 15, default: true },
        },
        plan_capabilities: {
          strategy_ids: '*',
          asset_classes: ['stocks', 'crypto'],
          timeframes: ['1D'],
        },
      })
    }

    if (path === '/api/auth/register' && method === 'POST') {
      return json({ user: adminUser, token: 'registered-token' }, 201)
    }

    if (path === '/api/auth/login' && method === 'POST') {
      return json({ user: adminUser, token: 'login-token' })
    }

    if (path === '/api/auth/me') {
      return json({ user: adminUser })
    }

    if (path === '/api/scan' && method === 'POST') {
      const payload = request.postDataJSON()
      scanRequests.push(payload)
      const jobId = `job-${scanRequests.length}`
      jobs.set(jobId, payload)
      return json({ job_id: jobId }, 202)
    }

    if (path.startsWith('/api/scan/status/job-')) {
      const jobId = path.split('/').at(-1)
      const payload = jobs.get(jobId)
      const meta = options.outcomeMeta || {
        total_scanned: 10,
        duration_seconds: 0.4,
        timeframe: payload.timeframe,
        market: payload.market,
        universe: payload.universe,
      }
      return json({
        job_id: jobId,
        status: 'completed',
        progress: 100,
        results: options.scanResults === undefined ? [scanResult] : options.scanResults,
        meta,
      })
    }

    if (path === '/api/watchlist' && method === 'POST') {
      watchlist.splice(0, watchlist.length, {
        id: 1,
        provider_symbol: 'AAPL',
        display_symbol: 'AAPL',
        symbol: 'AAPL',
        market: 'stocks',
        notes: '',
      })
      return json({ message: 'AAPL added to watchlist', id: 1 }, 201)
    }

    if (path === '/api/watchlist' && method === 'GET') {
      return json({ watchlist })
    }

    if (path === '/api/notifications' && method === 'GET') {
      return json({ notifications: [], unread_count: 0 })
    }

    if (path === '/api/admin/stats') {
      return json({ total_users: 1, active_users: 1, total_scans: 1, cache_entries: 0 })
    }

    if (path === '/api/admin/users') {
      return json({ users: [adminUser] })
    }

    if (path === '/api/admin/scans') {
      return json({
        scans: [
          {
            id: 1,
            date: '2026-07-05T00:00:00',
            market: 'stocks',
            total_scanned: 10,
            total_matched: 1,
            duration: 0.4,
          },
        ],
      })
    }

    if (path === '/api/admin/audit-logs') {
      return json({ audit_logs: [] })
    }

    return json({ error: `Unhandled mock route: ${method} ${path}` }, 404)
  })

  return { scanRequests }
}

test('registers, logs in, runs a scan, adds to watchlist, and views admin panel', async ({ page }) => {
  const consoleErrors = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })

  await mockApi(page)
  await page.goto('/')

  await expect(page.getByText('API Connected')).toBeVisible()

  await page.getByRole('button', { name: /sign in/i }).click()
  await page.getByRole('button', { name: /sign up/i }).click()
  await page.getByPlaceholder('Choose a username').fill('admin_user')
  await page.getByPlaceholder('your@email.com').fill(adminUser.email)
  await page.locator('input[type="password"]').nth(0).fill('Password123')
  await page.locator('input[type="password"]').nth(1).fill('Password123')
  await page.getByRole('button', { name: /create account/i }).click()

  await expect(page.getByRole('button', { name: /admin_user/i })).toBeVisible()

  await page.getByRole('button', { name: /admin_user/i }).click()
  await page.getByRole('button', { name: /sign out/i }).click()
  await page.getByRole('button', { name: /sign in/i }).click()
  await page.getByPlaceholder('your@email.com').fill(adminUser.email)
  await page.locator('input[type="password"]').first().fill('Password123')
  await page.locator('form').getByRole('button', { name: /^sign in$/i }).click()

  await expect(page.getByRole('button', { name: /admin_user/i })).toBeVisible()

  await page.getByRole('button', { name: /Crypto$/i }).click()
  await expect(page.getByPlaceholder(/Search crypto/i)).toBeVisible()
  await page.getByRole('button', { name: /Stocks$/i }).click()
  await expect(page.getByPlaceholder(/Search stocks/i)).toBeVisible()

  await page.getByRole('button', { name: /RSI Oversold/i }).click()
  await page.getByRole('button', { name: /run scan \(1 filter\)/i }).click()

  await expect(page.getByText('AAPL').first()).toBeVisible()
  await page.locator('tr', { hasText: 'AAPL' }).first().hover()
  await page.getByTitle('Add to watchlist').click()

  await page.getByRole('button', { name: 'Watchlist', exact: true }).click()
  await expect(page.getByText('Watchlist').first()).toBeVisible()
  await expect(page.getByText('AAPL')).toBeVisible()

  await page.getByRole('button', { name: /^admin$/i }).click()
  await expect(page.getByText('Admin Panel')).toBeVisible()
  await expect(page.getByText('Total Users')).toBeVisible()
  await page.getByRole('button', { name: /users/i }).click()
  await expect(page.getByText(adminUser.email)).toBeVisible()

  expect(consoleErrors).toEqual([])
})

test('requests every registered universe and preserves completed result labels', async ({ page }) => {
  const { scanRequests } = await mockApi(page)
  await page.goto('/')

  await page.getByRole('button', { name: /^RSI Oversold$/i }).click()
  for (const [label, universe] of [
    ['All US Top Volume', 'us_stocks_top'],
    ['NASDAQ Top Volume', 'nasdaq_top'],
    ['NYSE Top Volume', 'nyse_top'],
  ]) {
    await page.getByRole('radio', { name: new RegExp(label, 'i') }).click()
    await page.getByRole('button', { name: /run scan \(1 filter\)/i }).click()
    await expect.poll(() => scanRequests.at(-1)?.universe).toBe(universe)
    await expect(page.getByText('AAPL').first()).toBeVisible()
  }

  await expect(page.getByText(/Stocks · NYSE Top Volume · 1D/)).toBeVisible()
  await page.getByRole('button', { name: /Crypto$/i }).click()
  await expect(page.getByText(/Stocks · NYSE Top Volume · 1D/)).toBeVisible()
  await expect(page.getByText('AAPL').first()).toBeVisible()

  await page.getByRole('button', { name: /^RSI Oversold$/i }).click()
  await page.getByRole('radio', { name: /Crypto Top USD Pairs/i }).click()
  await page.getByRole('button', { name: /run scan \(1 filter\)/i }).click()
  await expect.poll(() => scanRequests.at(-1)?.universe).toBe('crypto_static')

  expect(scanRequests.map(request => request.universe)).toEqual([
    'us_stocks_top', 'nasdaq_top', 'nyse_top', 'crypto_static',
  ])
  expect(scanRequests.every(request => request.filters[0] === 'rsi_oversold')).toBe(true)
})

test('renders insufficient data and provider failure separately from no signal', async ({ page }) => {
  await mockApi(page, {
    scanResults: [],
    outcomeMeta: {
      total_scanned: 1,
      duration_seconds: 0.2,
      timeframe: '1D',
      market: 'stocks',
      universe: 'us_stocks_top',
      symbol_outcomes: [
        { symbol: 'MSFT', status: 'not_matched' },
        { symbol: 'AAPL', status: 'insufficient_data', closed_bars: 60, required_bars: 200 },
      ],
      provider_failures: 1,
      persistence_failures: [],
    },
  })
  await page.goto('/')
  await page.getByRole('button', { name: /^RSI Oversold$/i }).click()
  await page.getByRole('button', { name: /run scan \(1 filter\)/i }).click()

  await expect(page.getByTestId('outcome-not-matched')).toBeVisible()
  await expect(page.getByTestId('outcome-insufficient')).toContainText('60 of 200 closed bars')
  await expect(page.getByTestId('outcome-provider-failure')).toContainText('not a valid no-signal')
})

test('shows unsupported capability combinations as disabled controls', async ({ page }) => {
  await mockApi(page)
  await page.goto('/')
  await page.getByRole('button', { name: /Crypto$/i }).click()

  const unsupported = page.getByRole('button', { name: /Equity Only Strategy — Not supported for crypto/i })
  await expect(unsupported).toBeVisible()
  await expect(unsupported).toBeDisabled()
})
