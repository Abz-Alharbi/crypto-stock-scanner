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

async function mockApi(page) {
  const watchlist = []

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
              name: 'RSI Oversold',
              description: 'RSI below 30',
              category: 'oscillators',
            },
          },
        },
        presets: {},
        timeframes: {
          '1D': { label: '1 Day', short_label: '1D', available: true },
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
      return json({ job_id: 'job-1' }, 202)
    }

    if (path === '/api/scan/status/job-1') {
      return json({
        job_id: 'job-1',
        status: 'completed',
        progress: 100,
        results: [scanResult],
        meta: { total_scanned: 10, duration_seconds: 0.4, timeframe: '1D' },
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
