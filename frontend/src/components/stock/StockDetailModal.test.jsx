import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import StockDetailModal from './StockDetailModal'
import useMarketStore from '../../store/useMarketStore'

vi.mock('../charts/CandlestickChart', () => ({
  default: () => <div data-testid="mock-chart" />,
}))

const canonicalTimeframes = ['1m', '5m', '15m', '30m', '45m', '1H', '4H', '1D', '1W', '1M', '1Y']
const timeframeConfig = Object.fromEntries(
  canonicalTimeframes.map((key) => [
    key,
    {
      label: key,
      short_label: key,
      multiplier: key === '4H' ? 4 : key === '5m' ? 5 : key === '15m' ? 15 : key === '30m' ? 30 : key === '45m' ? 45 : 1,
      timespan: key.endsWith('m') ? 'minute' : key.endsWith('H') ? 'hour' : key === '1D' ? 'day' : key === '1W' ? 'week' : key === '1M' ? 'month' : 'year',
      category: ['1m', '5m', '15m', '30m', '45m', '1H', '4H'].includes(key) ? 'intraday' : 'higher',
    },
  ])
)

describe('Stock detail timeframe selector', () => {
  beforeEach(() => {
    useMarketStore.setState({
      isDetailOpen: true,
      selectedSymbol: 'AAPL',
      selectedProviderSymbol: 'AAPL',
      stockDetail: {
        name: 'Apple Inc.',
        market: 'stocks',
        analysis: {
          price: { last: 100, change_pct: 1, open: 99, high: 101, low: 98, volume: 1000 },
          indicators: {},
          patterns: { candlestick: [], chart: [] },
          fibonacci: {},
          signals: [],
        },
      },
      chartData: [{ t: 1, o: 99, h: 101, l: 98, c: 100, v: 1000 }],
      isLoadingDetail: false,
      isLoadingChart: false,
      detailError: null,
      watchlistError: null,
      timeframe: '1D',
      timeframes: timeframeConfig,
      closeDetail: vi.fn(),
      changeDetailTimeframe: vi.fn((timeframe) => useMarketStore.setState({ timeframe })),
      addToWatchlist: vi.fn(),
    })
  })

  it('renders and selects every canonical timeframe in the chart view', async () => {
    const user = userEvent.setup()
    render(<StockDetailModal />)

    for (const timeframe of canonicalTimeframes) {
      const button = screen.getByRole('button', { name: new RegExp(`^${timeframe}$`) })
      expect(button).toBeEnabled()
      await user.click(button)
      expect(useMarketStore.getState().changeDetailTimeframe).toHaveBeenCalledWith(timeframe)
    }
  })
})
