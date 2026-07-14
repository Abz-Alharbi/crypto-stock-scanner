import React from 'react'
import { beforeEach, describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import ScanResults from './ScanResults'
import useMarketStore from '../../store/useMarketStore'

const completedContext = {
  asset_class: 'stocks',
  scope: 'universe',
  universe: 'nasdaq_top',
  timeframe: '1D',
  strategy_ids: ['rsi_oversold'],
}

describe('scan result context and outcomes', () => {
  beforeEach(() => {
    useMarketStore.setState({
      activeMarket: 'stocks',
      activeUniverse: 'nasdaq_top',
      universes: {
        nasdaq_top: { key: 'nasdaq_top', name: 'NASDAQ Top Volume', asset_class: 'stocks' },
        crypto_static: { key: 'crypto_static', name: 'Crypto Top USD Pairs', asset_class: 'crypto' },
      },
      planCapabilities: { asset_classes: ['stocks', 'crypto'], timeframes: ['1D', '4H'], strategy_ids: '*' },
      marketSelections: {
        stocks: { universe: 'nasdaq_top', timeframe: '1D', filters: ['rsi_oversold'] },
        crypto: { universe: 'crypto_static', timeframe: '4H', filters: [] },
      },
      scanResults: [],
      scanMeta: null,
      scanContext: null,
      isScanning: false,
      scanError: null,
      watchlistError: null,
    })
  })

  it('does not relabel completed results after the active universe changes', () => {
    useMarketStore.setState({
      scanContext: completedContext,
      scanResults: [{
        provider_symbol: 'AAPL',
        display_symbol: 'AAPL',
        market: 'stocks',
        price: { last: 200, change_pct: 1 },
        overall_signal: 'bullish',
        match_pct: 100,
        patterns: [],
      }],
      scanMeta: {
        context: completedContext,
        market: 'stocks',
        universe: 'nasdaq_top',
        timeframe: '1D',
        total_scanned: 1,
        duration_seconds: 0.1,
      },
    })
    const { rerender } = render(<ScanResults />)

    expect(screen.getByText(/Stocks · NASDAQ Top Volume · 1D/)).toBeVisible()
    useMarketStore.getState().setMarket('crypto')
    rerender(<ScanResults />)

    expect(screen.getByText(/Stocks · NASDAQ Top Volume · 1D/)).toBeVisible()
    expect(screen.getByText('AAPL')).toBeVisible()
    expect(screen.queryByText(/Crypto · Crypto Top USD Pairs · 4H/)).not.toBeInTheDocument()
  })

  it('renders insufficiency, unsupported, errors, and infrastructure failures distinctly from no signal', () => {
    useMarketStore.setState({
      scanContext: completedContext,
      scanMeta: {
        context: completedContext,
        total_scanned: 1,
        duration_seconds: 0.2,
        symbol_outcomes: [
          { symbol: 'MSFT', status: 'not_matched' },
          { symbol: 'AAPL', status: 'insufficient_data', closed_bars: 60, required_bars: 200 },
          {
            symbol: 'OLD',
            status: 'unsupported',
            strategies: { pattern: { explanation: 'Pattern requires more history than 1Y provides' } },
          },
          { symbol: 'ERR', status: 'error', error: 'Technical analysis failed' },
        ],
        provider_failures: 1,
        persistence_failures: [{ stage: 'add_scan_result' }],
      },
    })

    render(<ScanResults />)

    expect(screen.getByTestId('outcome-not-matched')).toHaveTextContent('evaluated normally')
    expect(screen.getByTestId('outcome-insufficient')).toHaveTextContent('60 of 200 closed bars')
    expect(screen.getByTestId('outcome-unsupported')).toHaveTextContent('Pattern requires more history')
    expect(screen.getByTestId('outcome-error')).toHaveTextContent('Technical analysis failed')
    expect(screen.getByTestId('outcome-provider-failure')).toHaveTextContent('not a valid no-signal')
    expect(screen.getByTestId('outcome-persistence-failure')).toHaveTextContent('displayed results may be incomplete')
  })
})
