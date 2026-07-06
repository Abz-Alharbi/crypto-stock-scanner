import React, { useEffect, useState } from 'react';
import { BookmarkPlus, Trash2, Eye, AlertCircle, Pencil, Check, X } from 'lucide-react';
import useMarketStore from '../../store/useMarketStore';
import useAuthStore from '../../store/useAuthStore';
import LoadingSpinner from '../common/LoadingSpinner';

export default function WatchlistPage() {
  const { watchlist, isLoadingWatchlist, watchlistError, loadWatchlist, removeFromWatchlist, updateWatchlistNotes, openDetail } = useMarketStore();
  const { isAuthenticated, setAuthModal } = useAuthStore();
  const [editingId, setEditingId] = useState(null);
  const [notesDraft, setNotesDraft] = useState('');

  useEffect(() => {
    if (isAuthenticated) loadWatchlist();
  }, [isAuthenticated, loadWatchlist]);

  const startEditingNotes = (item) => {
    setEditingId(item.id);
    setNotesDraft(item.notes || '');
  };

  const cancelEditingNotes = () => {
    setEditingId(null);
    setNotesDraft('');
  };

  const saveNotes = async (itemId) => {
    try {
      await updateWatchlistNotes(itemId, notesDraft);
      cancelEditingNotes();
    } catch {
      // The store sets the visible watchlist error.
    }
  };

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

  if (watchlistError && watchlist.length === 0) {
    return (
      <div className="bg-scanner-card border border-scanner-danger/30 rounded-2xl p-8 text-center">
        <AlertCircle size={40} className="mx-auto text-scanner-danger mb-3" />
        <h3 className="font-display text-xl font-bold text-scanner-danger">Watchlist Error</h3>
        <p className="text-sm text-scanner-text-dim mt-2">{watchlistError}</p>
      </div>
    );
  }

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
        {watchlistError && (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-scanner-danger/30 bg-scanner-danger/10 px-3 py-2 text-xs text-scanner-danger">
            <AlertCircle size={14} />
            <span>{watchlistError}</span>
          </div>
        )}
      </div>
      <div className="divide-y divide-scanner-border/50">
        {watchlist.map((item) => {
          const providerSymbol = item.provider_symbol || item.symbol;
          const displaySymbol = item.market === 'crypto' ? providerSymbol : item.display_symbol || item.symbol;
          const isEditingNotes = editingId === item.id;
          return (
            <div key={item.id} className="px-5 py-4 hover:bg-scanner-bg/30 transition-colors group">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="font-mono font-bold text-scanner-text truncate">{displaySymbol}</span>
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-scanner-bg text-scanner-text-dim uppercase">{item.market}</span>
                </div>
                <div className="flex items-center gap-1 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => openDetail(providerSymbol)}
                    className="p-1.5 rounded-lg hover:bg-scanner-accent/10 text-scanner-text-dim hover:text-scanner-accent transition-colors"
                    title="View details"
                    aria-label={`View ${displaySymbol}`}
                  >
                    <Eye size={14} />
                  </button>
                  <button
                    onClick={() => startEditingNotes(item)}
                    className="p-1.5 rounded-lg hover:bg-scanner-accent/10 text-scanner-text-dim hover:text-scanner-accent transition-colors"
                    title="Edit notes"
                    aria-label={`Edit notes for ${displaySymbol}`}
                  >
                    <Pencil size={14} />
                  </button>
                  <button
                    onClick={() => removeFromWatchlist(item.id)}
                    className="p-1.5 rounded-lg hover:bg-scanner-danger/10 text-scanner-text-dim hover:text-scanner-danger transition-colors"
                    title="Remove from watchlist"
                    aria-label={`Remove ${displaySymbol}`}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              <div className="mt-3">
                {isEditingNotes ? (
                  <div className="flex items-start gap-2">
                    <textarea
                      value={notesDraft}
                      onChange={(event) => setNotesDraft(event.target.value)}
                      rows={2}
                      maxLength={1000}
                      className="min-h-16 flex-1 resize-none rounded-lg border border-scanner-border bg-scanner-bg px-3 py-2 text-sm text-scanner-text placeholder-scanner-text-dim focus:border-scanner-accent/50 focus:outline-none"
                      placeholder="Add notes..."
                    />
                    <div className="flex flex-col gap-1">
                      <button
                        onClick={() => saveNotes(item.id)}
                        className="p-1.5 rounded-lg hover:bg-scanner-accent/10 text-scanner-text-dim hover:text-scanner-accent transition-colors"
                        title="Save notes"
                        aria-label={`Save notes for ${displaySymbol}`}
                      >
                        <Check size={14} />
                      </button>
                      <button
                        onClick={cancelEditingNotes}
                        className="p-1.5 rounded-lg hover:bg-scanner-danger/10 text-scanner-text-dim hover:text-scanner-danger transition-colors"
                        title="Cancel editing notes"
                        aria-label={`Cancel notes edit for ${displaySymbol}`}
                      >
                        <X size={14} />
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => startEditingNotes(item)}
                    className="w-full rounded-lg border border-transparent px-3 py-2 text-left text-sm text-scanner-text-dim hover:border-scanner-border hover:bg-scanner-bg/40 transition-colors"
                  >
                    {item.notes ? item.notes : 'Add notes...'}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
