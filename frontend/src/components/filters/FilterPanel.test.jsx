import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import FilterPanel from './FilterPanel'
import useMarketStore from '../../store/useMarketStore'

const filters = {
  oscillators: {
    rsi_oversold: {
      name: 'RSI Oversold',
      description: 'RSI below 30',
      category: 'oscillators',
    },
  },
  moving_averages: {
    macd_bullish: {
      name: 'MACD Bullish',
      description: 'MACD line above signal line',
      category: 'moving_averages',
    },
  },
}

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

describe('Scanner filter panel', () => {
  beforeEach(() => {
    useMarketStore.setState({
      filterDefinitions: filters,
      filterPresets: {
        bullish_momentum: {
          name: 'Bullish Momentum',
          description: 'Momentum setup',
          filters: ['rsi_oversold', 'macd_bullish'],
        },
      },
      selectedFilters: [],
      timeframe: '1D',
      timeframes: timeframeConfig,
      isScanning: false,
      runScan: vi.fn(),
    })
  })

  it('selects filters, presets, and runs the scan action', async () => {
    const user = userEvent.setup()
    render(<FilterPanel />)

    expect(screen.getByRole('button', { name: /run scan \(0 filters\)/i })).toBeDisabled()

    await user.click(screen.getByText('RSI Oversold'))

    expect(useMarketStore.getState().selectedFilters).toEqual(['rsi_oversold'])
    expect(screen.getByRole('button', { name: /run scan \(1 filter\)/i })).toBeEnabled()

    await user.click(screen.getByText('Bullish Momentum'))

    expect(useMarketStore.getState().selectedFilters).toEqual(['rsi_oversold', 'macd_bullish'])

    for (const timeframe of canonicalTimeframes) {
      await user.click(screen.getByRole('button', { name: new RegExp(`^${timeframe}$`) }))
      expect(useMarketStore.getState().timeframe).toBe(timeframe)
    }

    await user.click(screen.getByRole('button', { name: /run scan \(2 filters\)/i }))
    expect(useMarketStore.getState().runScan).toHaveBeenCalled()
  })
})
