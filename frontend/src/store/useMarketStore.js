import { create } from 'zustand';
import { marketAPI, watchlistAPI } from '../services/api';

const useMarketStore = create((set, get) => ({
  // Market selection
  activeMarket: 'stocks', // stocks or crypto

  // Filters
  filterDefinitions: {},
  filterPresets: {},
  timeframes: {},
  selectedFilters: [],
  timeframe: '1D',

  // Scan state
  scanResults: [],
  scanMeta: null,
  isScanning: false,
  scanError: null,
  scanProgress: '',

  // Detail modal
  selectedSymbol: null,
  selectedProviderSymbol: null,
  stockDetail: null,
  chartData: [],
  isDetailOpen: false,
  isLoadingDetail: false,
  isLoadingChart: false,

  // Search
  searchResults: [],
  isSearching: false,

  // Watchlist
  watchlist: [],
  isLoadingWatchlist: false,

  // Connection
  isConnected: false,
  apiStatus: null,

  // ===== ACTIONS =====

  setMarket: (market) => set({ activeMarket: market }),

  setTimeframe: (tf) => set({ timeframe: tf }),

  toggleFilter: (filterKey) => {
    const current = get().selectedFilters;
    if (current.includes(filterKey)) {
      set({ selectedFilters: current.filter(f => f !== filterKey) });
    } else {
      set({ selectedFilters: [...current, filterKey] });
    }
  },

  setFiltersFromPreset: (presetKey) => {
    const preset = get().filterPresets[presetKey];
    if (preset) {
      set({ selectedFilters: [...preset.filters] });
    }
  },

  clearFilters: () => set({ selectedFilters: [] }),

  // Check API health
  checkConnection: async () => {
    try {
      const { data } = await marketAPI.health();
      set({ isConnected: true, apiStatus: data });
    } catch {
      set({ isConnected: false, apiStatus: null });
    }
  },

  // Load filter definitions from backend
  loadFilters: async () => {
    try {
      const { data } = await marketAPI.getFilters();
      set({
        filterDefinitions: data.filters,
        filterPresets: data.presets,
        timeframes: data.timeframes || {},
      });
    } catch (err) {
      console.error('Failed to load filters:', err);
    }
  },

  // Search tickers
  searchTickers: async (query) => {
    if (!query || query.length < 1) {
      set({ searchResults: [] });
      return;
    }
    set({ isSearching: true });
    try {
      const { data } = await marketAPI.search(query, get().activeMarket);
      set({ searchResults: data.results, isSearching: false });
    } catch {
      set({ searchResults: [], isSearching: false });
    }
  },

  // Run scan
  runScan: async () => {
    const { selectedFilters, activeMarket, timeframe } = get();
    if (selectedFilters.length === 0) {
      set({ scanError: 'Please select at least one filter' });
      return;
    }

    set({ isScanning: true, scanError: null, scanProgress: 'Starting scan...', scanResults: [], scanMeta: null });

    try {
      const { data } = await marketAPI.scan({
        market: activeMarket,
        filters: selectedFilters,
        timeframe: timeframe,
        limit: 30,
      });
      const jobId = data.job_id;
      let statusPayload = { status: 'queued', progress: 0 };

      while (!['completed', 'failed', 'canceled'].includes(statusPayload.status)) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        const response = await marketAPI.getScanStatus(jobId);
        statusPayload = response.data;
        set({
          scanResults: statusPayload.results || [],
          scanMeta: statusPayload.meta || null,
          scanProgress: `Scan ${statusPayload.status} (${statusPayload.progress || 0}%)`,
        });
      }

      if (statusPayload.status !== 'completed') {
        throw new Error(statusPayload.error || `Scan ${statusPayload.status}`);
      }

      set({
        scanResults: statusPayload.results || [],
        scanMeta: statusPayload.meta || null,
        isScanning: false,
        scanProgress: '',
      });
    } catch (err) {
      set({
        scanError: err.response?.data?.error || err.message || 'Scan failed. Check backend connection.',
        isScanning: false,
        scanProgress: '',
      });
    }
  },

  // Open stock detail
  openDetail: async (symbol) => {
    set({
      selectedSymbol: symbol,
      selectedProviderSymbol: symbol,
      isDetailOpen: true,
      isLoadingDetail: true,
      isLoadingChart: true,
      stockDetail: null,
      chartData: [],
    });

    try {
      const { data } = await marketAPI.getStockDetail(symbol, get().timeframe);
      set({
        selectedSymbol: data.display_symbol || data.symbol || symbol,
        selectedProviderSymbol: data.provider_symbol || data.raw_symbol || symbol,
        stockDetail: data,
        chartData: data.chart_data || [],
        isLoadingDetail: false,
        isLoadingChart: false,
      });
    } catch (err) {
      console.error('Failed to load detail:', err);
      set({ isLoadingDetail: false, isLoadingChart: false });
    }
  },

  closeDetail: () => set({ isDetailOpen: false, selectedSymbol: null, selectedProviderSymbol: null, stockDetail: null, chartData: [] }),

  // Change timeframe for detail view
  changeDetailTimeframe: async (tf) => {
    const { selectedSymbol, selectedProviderSymbol } = get();
    const providerSymbol = selectedProviderSymbol || selectedSymbol;
    if (!providerSymbol) return;
    set({ timeframe: tf, isLoadingChart: true });

    try {
      const { data } = await marketAPI.getStockDetail(providerSymbol, tf);
      set({
        selectedSymbol: data.display_symbol || data.symbol || selectedSymbol,
        selectedProviderSymbol: data.provider_symbol || data.raw_symbol || providerSymbol,
        stockDetail: data,
        chartData: data.chart_data || [],
        isLoadingChart: false,
      });
    } catch {
      set({ isLoadingChart: false });
    }
  },

  // Watchlist
  loadWatchlist: async () => {
    set({ isLoadingWatchlist: true });
    try {
      const { data } = await watchlistAPI.get();
      set({ watchlist: data.watchlist, isLoadingWatchlist: false });
    } catch {
      set({ isLoadingWatchlist: false });
    }
  },

  addToWatchlist: async (symbol, market) => {
    try {
      await watchlistAPI.add({ symbol, market });
      get().loadWatchlist();
    } catch (err) {
      console.error('Failed to add to watchlist:', err);
    }
  },

  removeFromWatchlist: async (id) => {
    try {
      await watchlistAPI.remove(id);
      get().loadWatchlist();
    } catch (err) {
      console.error('Failed to remove from watchlist:', err);
    }
  },
}));

export default useMarketStore;
