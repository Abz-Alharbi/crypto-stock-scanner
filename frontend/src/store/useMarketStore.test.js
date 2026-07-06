import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { waitFor } from '@testing-library/react'

const apiMocks = vi.hoisted(() => ({
  marketAPI: {
    health: vi.fn(),
    getFilters: vi.fn(),
    search: vi.fn(),
    scan: vi.fn(),
    getScanStatus: vi.fn(),
    getStockDetail: vi.fn(),
  },
  watchlistAPI: {
    get: vi.fn(),
    add: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
  },
}))

vi.mock('../services/api', () => ({
  marketAPI: apiMocks.marketAPI,
  watchlistAPI: apiMocks.watchlistAPI,
}))

import useMarketStore from './useMarketStore'

const resetMarketStore = () => {
  useMarketStore.setState({
    activeMarket: 'stocks',
    filterDefinitions: {},
    filterPresets: {},
    timeframes: {},
    selectedFilters: [],
    timeframe: '1D',
    scanResults: [],
    scanMeta: null,
    isScanning: false,
    scanError: null,
    scanProgress: '',
    selectedSymbol: null,
    selectedProviderSymbol: null,
    stockDetail: null,
    chartData: [],
    isDetailOpen: false,
    isLoadingDetail: false,
    isLoadingChart: false,
    searchResults: [],
    isSearching: false,
    watchlist: [],
    isLoadingWatchlist: false,
    isConnected: false,
    apiStatus: null,
  })
}

describe('watchlist store', () => {
  beforeEach(resetMarketStore)

  it('loads, edits notes, and removes watchlist items through the API client', async () => {
    apiMocks.watchlistAPI.get.mockResolvedValue({
      data: {
        watchlist: [{ id: 7, provider_symbol: 'X:BTCUSD', display_symbol: 'X:BTCUSD', market: 'crypto', notes: '' }],
      },
    })
    apiMocks.watchlistAPI.update.mockResolvedValue({
      data: {
        watchlist_item: { id: 7, provider_symbol: 'X:BTCUSD', display_symbol: 'X:BTCUSD', market: 'crypto', notes: 'watch closely' },
      },
    })
    apiMocks.watchlistAPI.remove.mockResolvedValue({ data: { message: 'Removed' } })

    await useMarketStore.getState().loadWatchlist()

    expect(useMarketStore.getState().watchlist).toHaveLength(1)
    expect(useMarketStore.getState().isLoadingWatchlist).toBe(false)

    await useMarketStore.getState().updateWatchlistNotes(7, 'watch closely')

    expect(apiMocks.watchlistAPI.update).toHaveBeenCalledWith(7, { notes: 'watch closely' })
    expect(useMarketStore.getState().watchlist[0]).toMatchObject({
      provider_symbol: 'X:BTCUSD',
      display_symbol: 'X:BTCUSD',
      notes: 'watch closely',
    })

    await useMarketStore.getState().removeFromWatchlist(7)

    expect(apiMocks.watchlistAPI.remove).toHaveBeenCalledWith(7)
    await waitFor(() => expect(apiMocks.watchlistAPI.get).toHaveBeenCalledTimes(2))
  })
})

describe('scan store', () => {
  beforeEach(() => {
    resetMarketStore()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('runs an async scan and stores completed results', async () => {
    apiMocks.marketAPI.scan.mockResolvedValueOnce({ data: { job_id: 'job-1' } })
    apiMocks.marketAPI.getScanStatus.mockResolvedValueOnce({
      data: {
        status: 'completed',
        progress: 100,
        results: [{ provider_symbol: 'AAPL', display_symbol: 'AAPL', market: 'stocks' }],
        meta: { total_scanned: 10, duration_seconds: 0.4, timeframe: '1D' },
      },
    })
    useMarketStore.setState({ selectedFilters: ['rsi_oversold'], activeMarket: 'stocks', timeframe: '1D' })

    const scanPromise = useMarketStore.getState().runScan()
    await Promise.resolve()

    expect(apiMocks.marketAPI.scan).toHaveBeenCalledWith({
      market: 'stocks',
      filters: ['rsi_oversold'],
      timeframe: '1D',
      limit: 30,
    })
    expect(useMarketStore.getState().isScanning).toBe(true)

    await vi.advanceTimersByTimeAsync(1000)
    await scanPromise

    expect(apiMocks.marketAPI.getScanStatus).toHaveBeenCalledWith('job-1')
    expect(useMarketStore.getState()).toMatchObject({
      isScanning: false,
      scanProgress: '',
      scanResults: [{ provider_symbol: 'AAPL', display_symbol: 'AAPL', market: 'stocks' }],
      scanMeta: { total_scanned: 10, duration_seconds: 0.4, timeframe: '1D' },
    })
  })

  it('sets a validation error when no filters are selected', async () => {
    await useMarketStore.getState().runScan()

    expect(apiMocks.marketAPI.scan).not.toHaveBeenCalled()
    expect(useMarketStore.getState().scanError).toBe('Please select at least one filter')
  })
})
