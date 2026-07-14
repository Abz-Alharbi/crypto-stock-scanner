import React, { useState } from 'react';
import { TrendingUp, TrendingDown, Minus, Eye, BookmarkPlus, AlertCircle, BarChart3, Clock } from 'lucide-react';
import useMarketStore from '../../store/useMarketStore';
import useAuthStore from '../../store/useAuthStore';
import LoadingSpinner, { SkeletonRow } from '../common/LoadingSpinner';
import TradeSetupCard from '../TradeSetupCard';

export default function ScanResults() {
  const { scanResults, scanMeta, scanContext, universes, isScanning, scanError, scanProgress, watchlistError, openDetail, addToWatchlist, activeMarket } = useMarketStore();
  const { isAuthenticated } = useAuthStore();
  const [expandedRow, setExpandedRow] = useState(null);
  const resultContext = scanMeta?.context || scanContext;
  const resultMarket = resultContext?.asset_class || resultContext?.assetClass || resultContext?.market || scanMeta?.market;
  const resultUniverse = resultContext?.universe || scanMeta?.universe;
  const resultTimeframe = resultContext?.timeframe || scanMeta?.timeframe;
  const contextLabel = resultContext
    ? `${resultMarket === 'crypto' ? 'Crypto' : 'Stocks'} · ${universes?.[resultUniverse]?.name || resultUniverse} · ${resultTimeframe}`
    : null;

  const toggleExpand = (symbol) => {
    setExpandedRow(expandedRow === symbol ? null : symbol);
  };

  if (scanError) {
    return (
      <div className="bg-scanner-card border border-scanner-danger/30 rounded-2xl p-8 text-center">
        <AlertCircle size={40} className="mx-auto text-scanner-danger mb-3" />
        <h3 className="text-lg font-semibold text-scanner-danger">Scan Failed</h3>
        <p className="text-sm text-scanner-text-dim mt-2">{scanError}</p>
      </div>
    );
  }

  if (isScanning) {
    return (
      <div className="bg-scanner-card border border-scanner-border rounded-2xl p-8">
        <LoadingSpinner size="lg" text={scanProgress || 'Scanning markets...'} />
        <div className="mt-4 max-w-md mx-auto">
          <div className="h-1.5 bg-scanner-bg rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-scanner-accent to-emerald-500 rounded-full animate-pulse" style={{ width: '60%' }} />
          </div>
          <p className="text-center text-[10px] text-scanner-text-dim mt-2">Scanning the configured universe with controlled Polygon concurrency</p>
        </div>
      </div>
    );
  }

  if (!scanResults || scanResults.length === 0) {
    if (scanMeta) {
      return (
        <div className="bg-scanner-card border border-scanner-border rounded-2xl p-8 text-center">
          <BarChart3 size={40} className="mx-auto text-scanner-text-dim mb-3" />
          <h3 className="text-lg font-semibold">No Matches Found</h3>
          <p className="text-sm text-scanner-text-dim mt-2">
            Scanned {scanMeta.total_scanned} {resultMarket} in {scanMeta.duration_seconds}s. Try different filters or timeframe.
          </p>
          {contextLabel && <p className="mt-2 text-xs font-medium text-scanner-accent" data-testid="scan-context">{contextLabel}</p>}
          {scanMeta.data_limit_notices?.length > 0 && (
            <div className="mt-4 inline-flex items-center gap-2 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-sm text-amber-300">
              <AlertCircle size={16} />
              <span>{scanMeta.data_limit_notices[0]}</span>
            </div>
          )}
          <OutcomeSummary meta={scanMeta} />
        </div>
      );
    }

    return (
      <div className="bg-scanner-card border border-scanner-border rounded-2xl p-12 text-center">
        <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-scanner-accent/10 flex items-center justify-center">
          <BarChart3 size={28} className="text-scanner-accent" />
        </div>
        <h3 className="font-display text-xl font-bold">Ready to Scan</h3>
        <p className="text-sm text-scanner-text-dim mt-2 max-w-md mx-auto">
          Select your filters on the left panel and hit "Run Scan" to find promising {activeMarket === 'stocks' ? 'stocks' : 'crypto'} matching your criteria.
        </p>
      </div>
    );
  }

  const signalIcon = (signal) => {
    if (signal === 'bullish') return <TrendingUp size={14} className="text-scanner-bullish" />;
    if (signal === 'bearish') return <TrendingDown size={14} className="text-scanner-bearish" />;
    return <Minus size={14} className="text-scanner-neutral" />;
  };

  const signalBadge = (signal) => {
    const cls = signal === 'bullish' ? 'signal-bullish' : signal === 'bearish' ? 'signal-bearish' : 'signal-neutral';
    return <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${cls}`}>{signalIcon(signal)} {signal}</span>;
  };

  return (
    <div className="bg-scanner-card border border-scanner-border rounded-2xl overflow-hidden">
      {watchlistError && (
        <div className="m-4 flex items-center gap-2 rounded-lg border border-scanner-danger/30 bg-scanner-danger/10 px-3 py-2 text-sm text-scanner-danger">
          <AlertCircle size={16} />
          <span>{watchlistError}</span>
        </div>
      )}

      {scanMeta?.data_limit_notices?.length > 0 && (
        <div className="m-4 flex items-center gap-2 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-sm text-amber-300">
          <AlertCircle size={16} />
          <span>{scanMeta.data_limit_notices[0]}</span>
        </div>
      )}

      <OutcomeSummary meta={scanMeta} />

      {/* Results Header */}
      {scanMeta && (
        <div className="px-5 py-3 border-b border-scanner-border bg-gradient-to-r from-scanner-card to-scanner-bg flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-3">
            <h3 className="font-display font-semibold">
              <span className="text-scanner-accent">{scanResults.length}</span> Match{scanResults.length !== 1 ? 'es' : ''}
            </h3>
            <span className="text-xs text-scanner-text-dim">
              from {scanMeta.total_scanned} scanned{contextLabel ? ` · ${contextLabel}` : ''}
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs text-scanner-text-dim">
            <Clock size={12} />
            {scanMeta.duration_seconds}s • {resultTimeframe}
          </div>
        </div>
      )}

      {/* Results Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[10px] uppercase tracking-widest text-scanner-text-dim border-b border-scanner-border">
              <th className="text-left px-5 py-3 font-medium">Symbol</th>
              <th className="text-right px-3 py-3 font-medium">Price</th>
              <th className="text-right px-3 py-3 font-medium">Change</th>
              <th className="text-center px-3 py-3 font-medium">Signal</th>
              <th className="text-center px-3 py-3 font-medium">Match</th>
              <th className="text-left px-3 py-3 font-medium hidden lg:table-cell">RSI</th>
              <th className="text-left px-3 py-3 font-medium hidden lg:table-cell">Patterns</th>
              <th className="text-right px-5 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {scanResults.map((result, idx) => {
              const providerSymbol = result.provider_symbol || result.raw_symbol || result.symbol;
              const displaySymbol = result.display_symbol || result.symbol;
              const rowKey = providerSymbol || `${displaySymbol}-${idx}`;
              return (
              <React.Fragment key={rowKey}>
                {/* Main Result Row */}
                <tr
                  className={`border-b border-scanner-border/50 hover:bg-scanner-bg/40 transition-colors cursor-pointer group ${expandedRow === rowKey ? 'bg-scanner-bg/30' : ''}`}
                  onClick={() => toggleExpand(rowKey)}
                  style={{ animationDelay: `${idx * 50}ms` }}
                >
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] transition-transform duration-200 text-scanner-text-dim ${expandedRow === rowKey ? 'rotate-90' : ''}`}>▶</span>
                      <span className="font-mono font-bold text-scanner-text group-hover:text-scanner-accent transition-colors">{displaySymbol}</span>
                      {result.market === 'crypto' && <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 font-medium">CRYPTO</span>}
                    </div>
                  </td>
                  <td className="text-right px-3 py-3 font-mono">${result.price?.last?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '—'}</td>
                  <td className={`text-right px-3 py-3 font-mono font-medium ${result.price?.change_pct >= 0 ? 'text-scanner-bullish' : 'text-scanner-bearish'}`}>
                    {result.price?.change_pct >= 0 ? '+' : ''}{result.price?.change_pct?.toFixed(2) || '0.00'}%
                  </td>
                  <td className="text-center px-3 py-3">{signalBadge(result.overall_signal)}</td>
                  <td className="text-center px-3 py-3">
                    <div className="flex items-center justify-center gap-1">
                      <div className="w-16 h-1.5 bg-scanner-bg rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-scanner-accent to-emerald-500"
                          style={{ width: `${result.match_pct}%` }}
                        />
                      </div>
                      <span className="text-[10px] font-mono text-scanner-accent">{result.match_pct}%</span>
                    </div>
                  </td>
                  <td className="px-3 py-3 hidden lg:table-cell">
                    <span className={`font-mono text-xs ${
                      result.rsi < 30 ? 'text-scanner-bullish' : result.rsi > 70 ? 'text-scanner-bearish' : 'text-scanner-text-dim'
                    }`}>
                      {result.rsi?.toFixed(1) || '—'}
                    </span>
                  </td>
                  <td className="px-3 py-3 hidden lg:table-cell">
                    <div className="flex flex-wrap gap-1">
                      {result.patterns?.slice(0, 2).map((p, i) => (
                        <span key={i} className="text-[9px] px-1.5 py-0.5 rounded bg-scanner-accent/10 text-scanner-accent">{p}</span>
                      ))}
                    </div>
                  </td>
                  <td className="text-right px-5 py-3">
                    <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={(e) => { e.stopPropagation(); openDetail(providerSymbol, resultContext); }}
                        className="p-1.5 rounded-lg hover:bg-scanner-accent/10 text-scanner-text-dim hover:text-scanner-accent transition-colors"
                        title="View details"
                      >
                        <Eye size={14} />
                      </button>
                      {isAuthenticated && (
                        <button
                          onClick={(e) => { e.stopPropagation(); addToWatchlist(providerSymbol, result.market); }}
                          className="p-1.5 rounded-lg hover:bg-scanner-accent/10 text-scanner-text-dim hover:text-scanner-accent transition-colors"
                          title="Add to watchlist"
                        >
                          <BookmarkPlus size={14} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>

                {/* Expandable Trade Setup Row */}
                {expandedRow === rowKey && (
                  <tr className="bg-scanner-bg/20">
                    <td colSpan={8} className="px-5 py-4">
                      <TradeSetupCard
                        trade_setup={result.trade_setup}
                        symbol={displaySymbol}
                        compact={false}
                      />
                    </td>
                  </tr>
                )}
              </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="border-t border-scanner-border bg-scanner-bg/30 px-5 py-3 text-center text-[10px] text-scanner-text-dim">
        Pattern detection is for research only and does not constitute financial advice.
      </div>
    </div>
  );
}

function OutcomeSummary({ meta }) {
  if (!meta) return null;
  const outcomes = meta.symbol_outcomes || [];
  const grouped = outcomes.reduce((counts, outcome) => {
    counts[outcome.status] = (counts[outcome.status] || 0) + 1;
    return counts;
  }, {});
  const insufficientOutcomes = outcomes.filter(outcome => outcome.status === 'insufficient_data');
  const outcomeSymbols = new Set(insufficientOutcomes.map(outcome => outcome.symbol));
  const insufficient = [
    ...insufficientOutcomes,
    ...(meta.insufficient_data_symbols || [])
      .filter(item => !outcomeSymbols.has(item.symbol))
      .map(item => ({
        symbol: item.symbol,
        status: 'insufficient_data',
        closed_bars: item.bars,
        required_bars: item.required,
      })),
  ];
  const unsupported = outcomes.filter(outcome => outcome.status === 'unsupported');
  const errors = outcomes.filter(outcome => outcome.status === 'error');
  const providerFailures = Number(meta.provider_failures || 0);
  const persistenceFailures = meta.persistence_failures || [];
  const hasDetails = insufficient.length || unsupported.length || errors.length || providerFailures || persistenceFailures.length;

  if (!hasDetails && !grouped.not_matched) return null;

  return (
    <div className="m-4 space-y-2 text-left" data-testid="scan-outcomes">
      {grouped.not_matched > 0 && (
        <OutcomeNotice tone="neutral" title="No signal" dataTestId="outcome-not-matched">
          {grouped.not_matched} symbol{grouped.not_matched === 1 ? '' : 's'} evaluated normally and did not match.
        </OutcomeNotice>
      )}
      {insufficient.map(outcome => (
        <OutcomeNotice key={`insufficient-${outcome.symbol}`} tone="warning" title={`Insufficient data · ${outcome.symbol}`} dataTestId="outcome-insufficient">
          {outcome.closed_bars ?? outcome.bars ?? 0} of {outcome.required_bars ?? 'required'} closed bars available.
        </OutcomeNotice>
      ))}
      {unsupported.map(outcome => (
        <OutcomeNotice key={`unsupported-${outcome.symbol}`} tone="purple" title={`Unsupported · ${outcome.symbol}`} dataTestId="outcome-unsupported">
          {outcomeReason(outcome, 'This strategy is unsupported for the selected context.')}
        </OutcomeNotice>
      ))}
      {errors.map(outcome => (
        <OutcomeNotice key={`error-${outcome.symbol}`} tone="danger" title={`Evaluation error · ${outcome.symbol}`} dataTestId="outcome-error">
          {outcome.error || outcomeReason(outcome, 'Strategy evaluation failed.')}
        </OutcomeNotice>
      ))}
      {providerFailures > 0 && (
        <OutcomeNotice tone="danger" title="Provider failure" dataTestId="outcome-provider-failure">
          Market data failed for {providerFailures} symbol{providerFailures === 1 ? '' : 's'}; this is not a valid no-signal result.
        </OutcomeNotice>
      )}
      {persistenceFailures.length > 0 && (
        <OutcomeNotice tone="danger" title="Persistence failure" dataTestId="outcome-persistence-failure">
          {persistenceFailures.length} result write{persistenceFailures.length === 1 ? '' : 's'} failed; displayed results may be incomplete.
        </OutcomeNotice>
      )}
    </div>
  );
}

function outcomeReason(outcome, fallback) {
  const strategy = Object.values(outcome.strategies || {}).find(item => item.explanation);
  return strategy?.explanation || fallback;
}

function OutcomeNotice({ tone, title, children, dataTestId }) {
  const tones = {
    neutral: 'border-scanner-border bg-scanner-bg/60 text-scanner-text-dim',
    warning: 'border-amber-400/30 bg-amber-400/10 text-amber-200',
    purple: 'border-purple-400/30 bg-purple-400/10 text-purple-200',
    danger: 'border-scanner-danger/40 bg-scanner-danger/10 text-scanner-danger',
  };
  return (
    <div className={`rounded-lg border px-3 py-2 text-xs ${tones[tone]}`} data-testid={dataTestId}>
      <p className="font-semibold">{title}</p>
      <p className="mt-0.5 opacity-90">{children}</p>
    </div>
  );
}
