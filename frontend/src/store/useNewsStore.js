import { create } from 'zustand';
import { newsAPI } from '../services/api';
import toast from 'react-hot-toast';

const useNewsStore = create((set, get) => ({
  // State
  articles: [],
  summary: {},
  sources: [],
  activeFeeds: [],
  sentimentEngine: '',
  total: 0,
  isLoading: false,
  error: null,
  currentSymbol: '',

  // Filters
  sentimentFilter: null,
  sourceFilter: null,
  daysFilter: 30,

  // Actions
  fetchNews: async (symbol) => {
    if (!symbol) return;
    const { sentimentFilter, sourceFilter, daysFilter } = get();

    set({ isLoading: true, error: null, currentSymbol: symbol.toUpperCase() });

    try {
      const params = { limit: 50, days: daysFilter };
      if (sentimentFilter) params.sentiment = sentimentFilter;
      if (sourceFilter) params.source = sourceFilter;

      const res = await newsAPI.getNews(symbol, params);
      const data = res.data;

      set({
        articles: data.articles || [],
        summary: data.summary || {},
        sources: data.sources || [],
        activeFeeds: data.active_feeds || [],
        sentimentEngine: data.sentiment_engine || 'lexicon',
        total: data.total || 0,
        isLoading: false,
      });
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to fetch news';
      set({ error: msg, isLoading: false, articles: [] });
      toast.error(msg);
    }
  },

  setSentimentFilter: (filter) => {
    set({ sentimentFilter: filter });
    const { currentSymbol } = get();
    if (currentSymbol) get().fetchNews(currentSymbol);
  },

  setSourceFilter: (source) => {
    set({ sourceFilter: source });
    const { currentSymbol } = get();
    if (currentSymbol) get().fetchNews(currentSymbol);
  },

  setDaysFilter: (days) => {
    set({ daysFilter: days });
    const { currentSymbol } = get();
    if (currentSymbol) get().fetchNews(currentSymbol);
  },

  clearFilters: () => {
    set({ sentimentFilter: null, sourceFilter: null, daysFilter: 30 });
    const { currentSymbol } = get();
    if (currentSymbol) get().fetchNews(currentSymbol);
  },

  reset: () => {
    set({
      articles: [], summary: {}, sources: [], activeFeeds: [], total: 0,
      isLoading: false, error: null, currentSymbol: '',
      sentimentFilter: null, sourceFilter: null, daysFilter: 30,
    });
  },
}));

export default useNewsStore;
