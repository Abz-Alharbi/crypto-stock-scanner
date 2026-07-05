import React, { useEffect } from 'react';
import { BookmarkPlus, Trash2, Eye, AlertCircle } from 'lucide-react';
import useMarketStore from '../../store/useMarketStore';
import useAuthStore from '../../store/useAuthStore';
import LoadingSpinner from '../common/LoadingSpinner';

export default function WatchlistPage() {
  const { watchlist, isLoadingWatchlist, loadWatchlist, removeFromWatchlist, openDetail } = useMarketStore();
  const { isAuthenticated, setAuthModal } = useAuthStore();

  useEffect(() => {
    if (isAuthenticated) loadWatchlist();
  }, [isAuthenticated]);

  if (!isAuthenticated) {
    return (
      <div className="bg-scanner-card border border-scanner-border rounded-2xl p-12 text-center">
        <BookmarkPlus size={48} className="mx-auto text-scanner-text-dim mb-4" />
        <h3 className="font-display text-xl font-bold">Sign In to Use Watchlist</h3>
        <p className="text-sm text-scanner-text-dim mt-2 mb-6">Create an account to save and track your favorite stocks and crypto.</p>
        <button
          onClick={() => setAuthModal(true, 'login')}
          className="px-6 py-2.5 rounded-lg bg-scanner-accent text-scanner-bg font-semibold text-sm hover:bg-scanner-accent/90 transition-all"
        >
          Sign In
        </button>
      </div>
    );
  }

  if (isLoadingWatchlist) return <LoadingSpinner text="Loading watchlist..." />;

  if (watchlist.length === 0) {
    return (
      <div className="bg-scanner-card border border-scanner-border rounded-2xl p-12 text-center">
        <BookmarkPlus size={48} className="mx-auto text-scanner-accent/30 mb-4" />
        <h3 className="font-display text-xl font-bold">Your Watchlist is Empty</h3>
        <p className="text-sm text-scanner-text-dim mt-2">Scan the market and add promising assets to track them here.</p>
      </div>
    );
  }

  return (
    <div className="bg-scanner-card border border-scanner-border rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b border-scanner-border">
        <h3 className="font-display font-semibold flex items-center gap-2">
          <BookmarkPlus size={18} className="text-scanner-accent" />
          Watchlist
          <span className="px-2 py-0.5 rounded-full bg-scanner-accent/10 text-scanner-accent text-xs font-mono">{watchlist.length}</span>
        </h3>
      </div>
      <div className="divide-y divide-scanner-border/50">
        {watchlist.map((item) => {
          const providerSymbol = item.provider_symbol || item.symbol;
          const displaySymbol = item.display_symbol || item.symbol;
          return (
          <div key={item.id} className="flex items-center justify-between px-5 py-3 hover:bg-scanner-bg/30 transition-colors group">
            <div className="flex items-center gap-3">
              <span className="font-mono font-bold text-scanner-text">{displaySymbol}</span>
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-scanner-bg text-scanner-text-dim uppercase">{item.market}</span>
            </div>
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={() => openDetail(providerSymbol)}
                className="p-1.5 rounded-lg hover:bg-scanner-accent/10 text-scanner-text-dim hover:text-scanner-accent transition-colors"
              >
                <Eye size={14} />
              </button>
              <button
                onClick={() => removeFromWatchlist(item.id)}
                className="p-1.5 rounded-lg hover:bg-scanner-danger/10 text-scanner-text-dim hover:text-scanner-danger transition-colors"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
          );
        })}
      </div>
    </div>
  );
}
