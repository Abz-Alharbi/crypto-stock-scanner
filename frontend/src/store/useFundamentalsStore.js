import { create } from 'zustand';
import { fundamentalsAPI } from '../services/api';
import toast from 'react-hot-toast';

const useFundamentalsStore = create((set, get) => ({
  data: null,
  isLoading: false,
  error: null,
  currentSymbol: '',

  fetchFundamentals: async (symbol) => {
    if (!symbol) return;
    set({ isLoading: true, error: null, currentSymbol: symbol.toUpperCase() });
    try {
      const res = await fundamentalsAPI.get(symbol);
      set({ data: res.data, isLoading: false });
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to fetch fundamental data';
      set({ error: msg, isLoading: false, data: null });
      toast.error(msg);
    }
  },

  reset: () => set({ data: null, isLoading: false, error: null, currentSymbol: '' }),
}));

export default useFundamentalsStore;
