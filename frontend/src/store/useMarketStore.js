import { create } from 'zustand';
import toast from 'react-hot-toast';
import { marketAPI, notificationAPI, scanTemplateAPI, watchlistAPI } from '../services/api';

const MAX_SCAN_WAIT_MS = 20 * 60 * 1000;
const MAX_QUEUED_WAIT_MS = 2 * 60 * 1000;

let searchAbortController = null;

const useMarketStore = create((set, get) => ({
  // Market selection
  activeMarket: 'stocks', // stocks or crypto

  // Filters
  filterDefinitions: {},
  filterPresets: {},
  timeframes: {},
  selectedFilters: [],
  timeframe: '1D',
  filterError: null,

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
  detailError: null,

  // Search
  searchResults: [],
  isSearching: false,

  // Watchlist
  watchlist: [],
  isLoadingWatchlist: false,
  watchlistError: null,

  // Scan templates
  scanTemplates: [],
  isSavingScanTemplate: false,
  scanTemplateError: null,

  // Notifications
  notifications: [],
  unreadNotificationCount: 0,
  isLoadingNotifications: false,
  notificationError: null,

  // Connection
  isConnected: false,
  apiStatus: null,

  // ===== ACTIONS =====

  setMarket: (market) => set({ activeMarket: market }),

  setTimeframe: (tf) => {
    const config = get().timeframes?.[tf];
    if (config?.available === false) return;
    set({ timeframe: tf });
  },

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
        filterError: null,
      });
    } catch (err) {
      const message = err.response?.data?.error || err.message || 'Failed to load filters';
      set({ filterError: message });
    }
  },

  // Search tickers
  searchTickers: async (query) => {
    searchAbortController?.abort();

    if (!query || query.length < 1) {
      searchAbortController = null;
      set({ searchResults: [], isSearching: false });
      return;
    }

    const controller = new AbortController();
    searchAbortController = controller;
    set({ isSearching: true });

    try {
      const { data } = await marketAPI.search(query, get().activeMarket, { signal: controller.signal });
      if (searchAbortController !== controller) return;
      set({ searchResults: data.results, isSearching: false });
    } catch (err) {
      if (controller.signal.aborted || err.code === 'ERR_CANCELED') return;
      set({ searchResults: [], isSearching: false });
    } finally {
      if (searchAbortController === controller) {
        searchAbortController = null;
      }
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
      const startedAt = Date.now();
      let queuedSince = Date.now();

      while (!['completed', 'failed', 'canceled'].includes(statusPayload.status)) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        const response = await marketAPI.getScanStatus(jobId);
        statusPayload = response.data;
        if (statusPayload.status !== 'queued') queuedSince = Date.now();

        if (Date.now() - startedAt > MAX_SCAN_WAIT_MS) {
          throw new Error('Scan timed out. Please try again with fewer filters or a smaller market.');
        }
        if (statusPayload.status === 'queued' && Date.now() - queuedSince > MAX_QUEUED_WAIT_MS) {
          throw new Error('Scan is still queued. The background worker may be unavailable; please try again shortly.');
        }

        const detail = statusPayload.current_symbol ? ` - ${statusPayload.current_symbol}` : '';
        set({
          scanResults: statusPayload.results || [],
          scanMeta: statusPayload.meta || null,
          scanProgress: `Scan ${statusPayload.status} (${statusPayload.progress || 0}%)${detail}`,
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
      detailError: null,
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
      const message = err.response?.data?.error || err.message || 'Failed to load detail';
      set({ detailError: message, isLoadingDetail: false, isLoadingChart: false });
    }
  },

  closeDetail: () => set({ isDetailOpen: false, selectedSymbol: null, selectedProviderSymbol: null, stockDetail: null, chartData: [], detailError: null }),

  // Change timeframe for detail view
  changeDetailTimeframe: async (tf) => {
    const { selectedSymbol, selectedProviderSymbol } = get();
    const config = get().timeframes?.[tf];
    if (config?.available === false) return;
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
        detailError: null,
      });
    } catch (err) {
      const message = err.response?.data?.error || err.message || 'Failed to load chart';
      set({ detailError: message, isLoadingChart: false });
    }
  },

  // Watchlist
  loadWatchlist: async () => {
    set({ isLoadingWatchlist: true });
    try {
      const { data } = await watchlistAPI.get();
      set({ watchlist: data.watchlist, isLoadingWatchlist: false, watchlistError: null });
    } catch (err) {
      const message = err.response?.data?.error || err.message || 'Failed to load watchlist';
      set({ isLoadingWatchlist: false, watchlistError: message });
    }
  },

  addToWatchlist: async (symbol, market) => {
    try {
      await watchlistAPI.add({ symbol, market });
      set({ watchlistError: null });
      get().loadWatchlist();
    } catch (err) {
      const message = err.response?.data?.error || err.message || 'Failed to add to watchlist';
      if (err.response?.status === 409 || err.response?.data?.code === 'duplicate_symbol') {
        toast.error(message);
      }
      set({ watchlistError: message });
    }
  },

  updateWatchlistNotes: async (id, notes) => {
    try {
      const { data } = await watchlistAPI.update(id, { notes });
      const updatedItem = data.watchlist_item;
      set({
        watchlist: get().watchlist.map(item => (item.id === id ? updatedItem : item)),
        watchlistError: null,
      });
    } catch (err) {
      const message = err.response?.data?.error || err.message || 'Failed to update watchlist notes';
      set({ watchlistError: message });
      throw err;
    }
  },

  removeFromWatchlist: async (id) => {
    try {
      await watchlistAPI.remove(id);
      set({ watchlistError: null });
      get().loadWatchlist();
    } catch (err) {
      const message = err.response?.data?.error || err.message || 'Failed to remove from watchlist';
      set({ watchlistError: message });
    }
  },

  loadScanTemplates: async () => {
    try {
      const { data } = await scanTemplateAPI.get();
      set({ scanTemplates: data.templates || [], scanTemplateError: null });
    } catch (err) {
      const message = err.response?.data?.error || err.message || 'Failed to load scan templates';
      set({ scanTemplateError: message });
    }
  },

  saveScanTemplate: async (name) => {
    const { selectedFilters, activeMarket, timeframe } = get();
    if (selectedFilters.length === 0) {
      set({ scanTemplateError: 'Select at least one filter before saving a template' });
      return;
    }

    set({ isSavingScanTemplate: true, scanTemplateError: null });
    try {
      const { data } = await scanTemplateAPI.create({
        name,
        market: activeMarket,
        timeframe,
        filters: selectedFilters,
        limit: 30,
      });
      set({
        scanTemplates: [data.template, ...get().scanTemplates],
        isSavingScanTemplate: false,
        scanTemplateError: null,
      });
      toast.success('Scan template saved');
    } catch (err) {
      const message = err.response?.data?.error || err.message || 'Failed to save scan template';
      set({ isSavingScanTemplate: false, scanTemplateError: message });
    }
  },

  loadNotifications: async () => {
    set({ isLoadingNotifications: true });
    try {
      const { data } = await notificationAPI.get();
      set({
        notifications: data.notifications || [],
        unreadNotificationCount: data.unread_count || 0,
        isLoadingNotifications: false,
        notificationError: null,
      });
    } catch (err) {
      const message = err.response?.data?.error || err.message || 'Failed to load notifications';
      set({ isLoadingNotifications: false, notificationError: message });
    }
  },

  markNotificationRead: async (id) => {
    try {
      const previous = get().notifications.find(item => item.id === id);
      const wasUnread = previous && !previous.is_read;
      const { data } = await notificationAPI.markRead(id);
      const updated = data.notification;
      set({
        notifications: get().notifications.map(item => (item.id === id ? updated : item)),
        unreadNotificationCount: Math.max(0, get().unreadNotificationCount - (wasUnread ? 1 : 0)),
        notificationError: null,
      });
    } catch (err) {
      const message = err.response?.data?.error || err.message || 'Failed to update notification';
      set({ notificationError: message });
    }
  },
}));

export default useMarketStore;
