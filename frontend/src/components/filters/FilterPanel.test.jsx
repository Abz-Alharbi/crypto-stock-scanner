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
      timeframes: {
        '1D': { label: '1 Day', short_label: '1D', available: true },
        '1W': { label: '1 Week', short_label: '1W', available: true },
      },
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

    await user.click(screen.getByRole('button', { name: /1W/i }))
    expect(useMarketStore.getState().timeframe).toBe('1W')

    await user.click(screen.getByRole('button', { name: /run scan \(2 filters\)/i }))
    expect(useMarketStore.getState().runScan).toHaveBeenCalled()
  })
})

