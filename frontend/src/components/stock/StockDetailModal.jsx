import React, { useMemo, useState } from 'react';
import { X, TrendingUp, TrendingDown, Minus, Activity, BarChart3, Target, Layers, BookmarkPlus, RefreshCw, ExternalLink, AlertCircle } from 'lucide-react';
import useMarketStore from '../../store/useMarketStore';
import useAuthStore from '../../store/useAuthStore';
import CandlestickChart from '../charts/CandlestickChart';
import LoadingSpinner from '../common/LoadingSpinner';

export default function StockDetailModal() {
  const { isDetailOpen, selectedSymbol, selectedProviderSymbol, stockDetail, chartData, isLoadingDetail, isLoadingChart, detailError, watchlistError, closeDetail, changeDetailTimeframe, timeframe, timeframes, addToWatchlist, activeMarket } = useMarketStore();
  const { isAuthenticated, setAuthModal } = useAuthStore();
  const [activeTab, setActiveTab] = useState('indicators');

  const analysis = stockDetail?.analysis;
  const price = analysis?.price;
  const indicators = analysis?.indicators;
  const chartIndicators = useMemo(() => indicators || {}, [indicators]);

  if (!isDetailOpen) return null;

  const isPositive = price?.change_pct >= 0;
  const timeframeOptions = Object.entries(timeframes || {}).map(([key, config]) => ({
    key,
    label: config.label || key,
    shortLabel: config.short_label || key,
    category: config.category || 'higher',
    available: config.available !== false,
  }));
  const intradayTimeframes = timeframeOptions.filter(tf => tf.category === 'intraday');
  const higherTimeframes = timeframeOptions.filter(tf => tf.category !== 'intraday');

  const tabs = [
    { key: 'indicators', label: 'Indicators', icon: Activity },
    { key: 'patterns', label: 'Patterns', icon: Layers },
    { key: 'fibonacci', label: 'Fibonacci', icon: Target },
    { key: 'signals', label: 'Signals', icon: BarChart3 },
  ];

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/80 backdrop-blur-sm animate-fade-in" onClick={closeDetail}>
      <div className="min-h-screen flex items-start justify-center p-4 pt-8">
        <div className="w-full max-w-5xl bg-scanner-surface border border-scanner-border rounded-2xl shadow-2xl animate-slide-up" onClick={e => e.stopPropagation()}>
          {/* Modal Header */}
          <div className="flex items-center justify-between p-5 border-b border-scanner-border">
            <div className="flex items-center gap-4">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="font-display text-2xl font-bold">{selectedSymbol}</h2>
                  {analysis?.overall_signal && (
                    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold uppercase ${
                      analysis.overall_signal === 'bullish' ? 'signal-bullish' : analysis.overall_signal === 'bearish' ? 'signal-bearish' : 'signal-neutral'
                    }`}>
                      {analysis.overall_signal === 'bullish' ? <TrendingUp size={12} /> : analysis.overall_signal === 'bearish' ? <TrendingDown size={12} /> : <Minus size={12} />}
                      {analysis.overall_signal}
                    </span>
                  )}
                </div>
                {stockDetail?.name && <p className="text-sm text-scanner-text-dim mt-0.5">{stockDetail.name}</p>}
              </div>
            </div>

            <div className="flex items-center gap-2">
              {price && (
                <div className="text-right mr-4">
                  <p className="font-mono text-2xl font-bold">${price.last?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                  <p className={`font-mono text-sm font-medium ${isPositive ? 'text-scanner-bullish' : 'text-scanner-bearish'}`}>
                    {isPositive ? '+' : ''}{price.change_pct?.toFixed(2)}%
                  </p>
                </div>
              )}
              {isAuthenticated && (
                <button
                  onClick={() => addToWatchlist(selectedProviderSymbol || selectedSymbol, stockDetail?.market || activeMarket)}
                  className="p-2 rounded-lg hover:bg-scanner-accent/10 text-scanner-text-dim hover:text-scanner-accent transition-colors"
                  title="Add to watchlist"
                >
                  <BookmarkPlus size={18} />
                </button>
              )}
              <button onClick={closeDetail} className="p-2 rounded-lg hover:bg-scanner-card transition-colors">
                <X size={18} className="text-scanner-text-dim" />
              </button>
            </div>
          </div>

          {/* Timeframe selector — Two rows */}
          <div className="px-5 py-3 border-b border-scanner-border space-y-2">
            {/* Row 1: Minutes */}
            <div className="flex items-center gap-1.5">
              <span className="text-[9px] text-scanner-text-dim uppercase tracking-widest w-14 shrink-0">Subday</span>
              {intradayTimeframes.map(tf => (
                <button
                  key={tf.key}
                  onClick={() => tf.available && changeDetailTimeframe(tf.key)}
                  disabled={!tf.available}
                  className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all ${
                    timeframe === tf.key
                      ? 'bg-scanner-accent text-scanner-bg shadow-sm shadow-scanner-accent/25'
                      : !tf.available
                        ? 'text-scanner-text-dim/40 bg-scanner-card/40 border border-dashed border-scanner-border cursor-not-allowed'
                        : 'text-scanner-text-dim hover:text-scanner-text hover:bg-scanner-card'
                  }`}
                  title={!tf.available ? 'Unavailable on the current data plan' : tf.label}
                >
                  {tf.shortLabel}
                </button>
              ))}
            </div>
            {/* Row 2: Hour+ */}
            <div className="flex items-center gap-1.5">
              <span className="text-[9px] text-scanner-text-dim uppercase tracking-widest w-14 shrink-0">Higher</span>
              {higherTimeframes.map(tf => (
                <button
                  key={tf.key}
                  onClick={() => tf.available && changeDetailTimeframe(tf.key)}
                  disabled={!tf.available}
                  className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all ${
                    timeframe === tf.key
                      ? 'bg-scanner-accent text-scanner-bg shadow-sm shadow-scanner-accent/25'
                      : !tf.available
                        ? 'text-scanner-text-dim/40 bg-scanner-card/40 border border-dashed border-scanner-border cursor-not-allowed'
                        : 'text-scanner-text-dim hover:text-scanner-text hover:bg-scanner-card'
                  }`}
                  title={!tf.available ? 'Unavailable on the current data plan' : tf.label}
                >
                  {tf.shortLabel}
                </button>
              ))}
            </div>
          </div>

          {(detailError || watchlistError) && (
            <div className="mx-5 mt-4 flex items-center gap-2 rounded-lg border border-scanner-danger/30 bg-scanner-danger/10 px-3 py-2 text-sm text-scanner-danger">
              <AlertCircle size={16} />
              <span>{detailError || watchlistError}</span>
            </div>
          )}

          {stockDetail?.data_limit_notice && !detailError && (
            <div className="mx-5 mt-4 flex items-center gap-2 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-sm text-amber-300">
              <AlertCircle size={16} />
              <span>{stockDetail.data_limit_notice}</span>
            </div>
          )}

          {isLoadingDetail ? (
            <div className="p-12"><LoadingSpinner size="lg" text="Loading analysis..." /></div>
          ) : (
            <>
              {/* Chart */}
              <div className="p-5 border-b border-scanner-border">
                {isLoadingChart ? (
                  <div className="h-[400px] flex items-center justify-center"><LoadingSpinner text="Loading chart..." /></div>
                ) : (
                  <CandlestickChart
                    data={chartData}
                    height={400}
                    indicators={chartIndicators}
                    symbol={selectedProviderSymbol || selectedSymbol}
                    timeframe={timeframe}
                    canDetectPatterns={isAuthenticated}
                    onPatternAuthRequired={() => setAuthModal(true, 'login')}
                  />
                )}
              </div>

              {/* Quick Stats Bar */}
              {price && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-scanner-border border-b border-scanner-border">
                  {[
                    { label: 'Open', value: `$${price.open?.toFixed(2)}` },
                    { label: 'High', value: `$${price.high?.toFixed(2)}` },
                    { label: 'Low', value: `$${price.low?.toFixed(2)}` },
                    { label: 'Volume', value: price.volume?.toLocaleString() || '—' },
                  ].map(({ label, value }) => (
                    <div key={label} className="bg-scanner-surface px-4 py-3 text-center">
                      <p className="text-[10px] text-scanner-text-dim uppercase tracking-wider">{label}</p>
                      <p className="font-mono text-sm font-medium mt-0.5">{value}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Tabs */}
              <div className="flex border-b border-scanner-border">
                {tabs.map(({ key, label, icon: Icon }) => (
                  <button
                    key={key}
                    onClick={() => setActiveTab(key)}
                    className={`flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-all ${
                      activeTab === key
                        ? 'border-scanner-accent text-scanner-accent'
                        : 'border-transparent text-scanner-text-dim hover:text-scanner-text'
                    }`}
                  >
                    <Icon size={14} /> {label}
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              <div className="p-5">
                {activeTab === 'indicators' && indicators && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {/* RSI */}
                    <IndicatorCard title="RSI (14)" value={indicators.rsi?.toFixed(1)} status={indicators.rsi < 30 ? 'bullish' : indicators.rsi > 70 ? 'bearish' : 'neutral'}
                      detail={indicators.rsi < 30 ? 'Oversold' : indicators.rsi > 70 ? 'Overbought' : 'Neutral'} />

                    {/* MACD */}
                    <IndicatorCard title="MACD" value={indicators.macd?.line?.toFixed(4)} status={indicators.macd?.line > indicators.macd?.signal ? 'bullish' : 'bearish'}
                      detail={`Signal: ${indicators.macd?.signal?.toFixed(4) || '—'} | Hist: ${indicators.macd?.histogram?.toFixed(4) || '—'}`} />

                    {/* EMA */}
                    <IndicatorCard title="EMA 50 / 200" value={`${indicators.ema?.ema_50?.toFixed(2) || '—'} / ${indicators.ema?.ema_200?.toFixed(2) || '—'}`}
                      status={indicators.ema?.ema_50 > indicators.ema?.ema_200 ? 'bullish' : 'bearish'}
                      detail={indicators.ema?.ema_50 > indicators.ema?.ema_200 ? 'Golden Cross' : 'Death Cross'} />

                    {/* SMA */}
                    <IndicatorCard title="SMA 20 / 50 / 200"
                      value={`${indicators.sma?.sma_20?.toFixed(2) || '—'}`}
                      status={price?.last > indicators.sma?.sma_200 ? 'bullish' : 'bearish'}
                      detail={`50: ${indicators.sma?.sma_50?.toFixed(2) || '—'} | 200: ${indicators.sma?.sma_200?.toFixed(2) || '—'}`} />

                    {/* Bollinger Bands */}
                    <IndicatorCard title="Bollinger Bands"
                      value={`${indicators.bollinger_bands?.middle?.toFixed(2) || '—'}`}
                      status={price?.last <= indicators.bollinger_bands?.lower * 1.02 ? 'bullish' : price?.last >= indicators.bollinger_bands?.upper * 0.98 ? 'bearish' : 'neutral'}
                      detail={`Upper: ${indicators.bollinger_bands?.upper?.toFixed(2) || '—'} | Lower: ${indicators.bollinger_bands?.lower?.toFixed(2) || '—'}`} />

                    {/* Stochastic */}
                    <IndicatorCard title="Stochastic (%K/%D)"
                      value={`${indicators.stochastic?.k?.toFixed(1) || '—'} / ${indicators.stochastic?.d?.toFixed(1) || '—'}`}
                      status={indicators.stochastic?.k < 20 ? 'bullish' : indicators.stochastic?.k > 80 ? 'bearish' : 'neutral'}
                      detail={indicators.stochastic?.k < 20 ? 'Oversold' : indicators.stochastic?.k > 80 ? 'Overbought' : 'Neutral zone'} />
                  </div>
                )}

                {activeTab === 'patterns' && analysis?.patterns && (
                  <div className="space-y-4">
                    <div>
                      <h4 className="text-xs uppercase tracking-wider text-scanner-text-dim font-medium mb-3">Candlestick Patterns</h4>
                      {analysis.patterns.candlestick.length > 0 ? (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {analysis.patterns.candlestick.map((p, i) => (
                            <div key={i} className={`flex items-center justify-between p-3 rounded-lg border ${
                              p.type === 'bullish' ? 'bg-scanner-bullish/5 border-scanner-bullish/20' :
                              p.type === 'bearish' ? 'bg-scanner-bearish/5 border-scanner-bearish/20' :
                              'bg-scanner-card border-scanner-border'
                            }`}>
                              <span className="text-sm font-medium">{p.pattern}</span>
                              <div className="flex items-center gap-2">
                                <span className={`text-[10px] uppercase font-bold ${p.type === 'bullish' ? 'text-scanner-bullish' : p.type === 'bearish' ? 'text-scanner-bearish' : 'text-scanner-neutral'}`}>{p.type}</span>
                                <span className="text-[9px] px-1.5 py-0.5 rounded bg-scanner-bg text-scanner-text-dim">{p.strength}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : <p className="text-sm text-scanner-text-dim">No candlestick patterns detected</p>}
                    </div>
                    <div>
                      <h4 className="text-xs uppercase tracking-wider text-scanner-text-dim font-medium mb-3">Chart Patterns</h4>
                      {analysis.patterns.chart.length > 0 ? (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {analysis.patterns.chart.map((p, i) => (
                            <div key={i} className={`flex items-center justify-between p-3 rounded-lg border ${
                              p.type === 'bullish' ? 'bg-scanner-bullish/5 border-scanner-bullish/20' : 'bg-scanner-bearish/5 border-scanner-bearish/20'
                            }`}>
                              <span className="text-sm font-medium">{p.pattern}</span>
                              <span className={`text-[10px] uppercase font-bold ${p.type === 'bullish' ? 'text-scanner-bullish' : 'text-scanner-bearish'}`}>{p.type}</span>
                            </div>
                          ))}
                        </div>
                      ) : <p className="text-sm text-scanner-text-dim">No chart patterns detected in this timeframe</p>}
                    </div>
                  </div>
                )}

                {activeTab === 'fibonacci' && analysis?.fibonacci && (
                  <div className="space-y-4">
                    {/* Fibonacci Position Summary */}
                    {analysis.fibonacci.price_zone && (
                      <div className="p-4 rounded-xl bg-scanner-accent/5 border border-scanner-accent/20">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-[10px] uppercase tracking-widest text-scanner-accent font-medium">Position</span>
                          <div className="flex items-center gap-2">
                            {analysis.fibonacci.trend && (
                              <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold ${
                                analysis.fibonacci.trend === 'uptrend' ? 'bg-scanner-bullish/10 text-scanner-bullish' : 'bg-scanner-bearish/10 text-scanner-bearish'
                              }`}>
                                {analysis.fibonacci.trend === 'uptrend' ? '▲ Uptrend' : '▼ Downtrend'}
                              </span>
                            )}
                            <span className="font-mono text-sm font-bold text-scanner-accent">{analysis.fibonacci.retracement_pct}% retrace</span>
                          </div>
                        </div>
                        <p className="text-xs text-scanner-text-dim">{analysis.fibonacci.price_zone_desc}</p>
                        {/* Visual bar */}
                        <div className="mt-3">
                          <div className="flex justify-between text-[8px] font-mono text-scanner-text-dim mb-1">
                            <span>0%</span><span>23.6</span><span>38.2</span>
                            <span className="text-scanner-accent font-bold">50</span>
                            <span className="text-scanner-accent font-bold">61.8</span>
                            <span>78.6</span><span>100%</span>
                          </div>
                          <div className="h-2.5 rounded-full bg-scanner-bg relative overflow-hidden">
                            <div className="absolute h-full opacity-20 bg-scanner-accent" style={{ left: '50%', width: '11.8%' }} />
                            <div className="absolute h-full w-1.5 rounded-full bg-scanner-accent" 
                              style={{ left: `${Math.min(100, Math.max(0, analysis.fibonacci.retracement_pct))}%`, transform: 'translateX(-50%)', boxShadow: '0 0 8px var(--color-accent, #6366f1)' }} />
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Range info */}
                    <div className="flex gap-3">
                      <div className="flex-1 p-3 rounded-lg bg-scanner-card border border-scanner-border text-center">
                        <p className="text-[9px] text-scanner-text-dim uppercase">Swing High</p>
                        <p className="font-mono text-sm font-bold text-scanner-bearish">${analysis.fibonacci.swing_high?.toFixed(2)}</p>
                      </div>
                      <div className="flex-1 p-3 rounded-lg bg-scanner-card border border-scanner-border text-center">
                        <p className="text-[9px] text-scanner-text-dim uppercase">Swing Low</p>
                        <p className="font-mono text-sm font-bold text-scanner-bullish">${analysis.fibonacci.swing_low?.toFixed(2)}</p>
                      </div>
                      <div className="flex-1 p-3 rounded-lg bg-scanner-card border border-scanner-border text-center">
                        <p className="text-[9px] text-scanner-text-dim uppercase">Range</p>
                        <p className="font-mono text-sm font-bold">${analysis.fibonacci.range?.toFixed(2)} <span className="text-scanner-text-dim text-[10px]">({analysis.fibonacci.range_pct}%)</span></p>
                      </div>
                    </div>

                    {/* Retracement Levels */}
                    <div>
                      <h4 className="text-[10px] uppercase tracking-widest text-scanner-text-dim font-medium mb-2">Retracement Levels</h4>
                      <div className="space-y-1">
                        {[
                          { key: 'level_0', label: '0% (High)' },
                          { key: 'level_146', label: '14.6%' },
                          { key: 'level_236', label: '23.6%' },
                          { key: 'level_382', label: '38.2%', highlight: true },
                          { key: 'level_500', label: '50.0%', highlight: true },
                          { key: 'level_618', label: '61.8%', highlight: true },
                          { key: 'level_707', label: '70.7%' },
                          { key: 'level_786', label: '78.6%' },
                          { key: 'level_886', label: '88.6%' },
                          { key: 'level_100', label: '100% (Low)' },
                        ].map(({ key, label, highlight }) => {
                          const val = analysis.fibonacci[key];
                          if (val == null) return null;
                          const isNearPrice = Math.abs(price?.last - val) / price?.last < 0.012;
                          return (
                            <div key={key} className={`flex items-center justify-between px-3 py-2 rounded-lg border transition-all ${
                              isNearPrice ? 'bg-scanner-accent/10 border-scanner-accent/30 ring-1 ring-scanner-accent/20' :
                              highlight ? 'bg-scanner-card border-scanner-border' :
                              'border-transparent'
                            }`}>
                              <div className="flex items-center gap-2">
                                <span className={`text-xs font-mono ${highlight ? 'text-scanner-text font-semibold' : 'text-scanner-text-dim'}`} style={{ width: '70px' }}>{label}</span>
                                {isNearPrice && <span className="text-[8px] px-1.5 py-0.5 rounded-full bg-scanner-accent/20 text-scanner-accent font-bold animate-pulse">◉ PRICE</span>}
                                {highlight && !isNearPrice && <span className="text-[8px] text-scanner-accent/40">★</span>}
                              </div>
                              <span className={`font-mono text-sm ${highlight ? 'font-semibold' : ''}`}>${val.toFixed(2)}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Extension Levels */}
                    <div>
                      <h4 className="text-[10px] uppercase tracking-widest text-scanner-text-dim font-medium mb-2">Extension Levels (Targets)</h4>
                      <div className="space-y-1">
                        {[
                          { key: 'ext_1272', label: '127.2%', highlight: true },
                          { key: 'ext_1414', label: '141.4%' },
                          { key: 'ext_1618', label: '161.8%', highlight: true },
                          { key: 'ext_2000', label: '200.0%', highlight: true },
                          { key: 'ext_2272', label: '227.2%' },
                          { key: 'ext_2618', label: '261.8%', highlight: true },
                          { key: 'ext_3146', label: '314.6%' },
                          { key: 'ext_4236', label: '423.6%' },
                        ].map(({ key, label, highlight }) => {
                          const val = analysis.fibonacci[key];
                          if (val == null) return null;
                          const isTarget = val > price?.last;
                          return (
                            <div key={key} className={`flex items-center justify-between px-3 py-2 rounded-lg border ${
                              highlight ? 'bg-scanner-card border-scanner-border' : 'border-transparent'
                            }`}>
                              <div className="flex items-center gap-2">
                                <span className={`text-xs font-mono ${highlight ? 'text-scanner-text font-semibold' : 'text-scanner-text-dim'}`} style={{ width: '70px' }}>{label}</span>
                                {isTarget && highlight && <span className="text-[8px] px-1.5 py-0.5 rounded bg-scanner-bullish/10 text-scanner-bullish font-medium">TARGET</span>}
                                {highlight && <span className="text-[8px] text-scanner-accent/40">★</span>}
                              </div>
                              <span className={`font-mono text-sm ${highlight ? 'font-semibold' : ''}`}>${val.toFixed(2)}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Confluence Zones */}
                    {analysis.fibonacci.zones?.length > 0 && (
                      <div>
                        <h4 className="text-[10px] uppercase tracking-widest text-scanner-text-dim font-medium mb-2">Confluence Zones (Multi-Level Clusters)</h4>
                        <div className="space-y-2">
                          {analysis.fibonacci.zones.map((zone, i) => (
                            <div key={i} className={`flex items-center justify-between p-3 rounded-lg border ${
                              zone.type === 'support' ? 'bg-scanner-bullish/5 border-scanner-bullish/20' : 'bg-scanner-bearish/5 border-scanner-bearish/20'
                            }`}>
                              <div className="flex items-center gap-2">
                                <span className={`text-[10px] uppercase font-bold ${zone.type === 'support' ? 'text-scanner-bullish' : 'text-scanner-bearish'}`}>{zone.type}</span>
                                <span className="text-[9px] px-1.5 py-0.5 rounded bg-scanner-bg text-scanner-text-dim">{zone.strength} levels</span>
                              </div>
                              <span className="font-mono text-sm font-medium">${zone.low.toFixed(2)} — ${zone.high.toFixed(2)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Nearest S/R */}
                    <div className="grid grid-cols-2 gap-3">
                      {analysis.fibonacci.nearest_support && (
                        <div className="p-3 rounded-lg bg-scanner-bullish/5 border border-scanner-bullish/20">
                          <p className="text-[9px] text-scanner-text-dim uppercase mb-1">Nearest Fib Support</p>
                          <p className="text-scanner-bullish font-mono text-lg font-bold">${analysis.fibonacci.nearest_support.toFixed(2)}</p>
                        </div>
                      )}
                      {analysis.fibonacci.nearest_resistance && (
                        <div className="p-3 rounded-lg bg-scanner-bearish/5 border border-scanner-bearish/20">
                          <p className="text-[9px] text-scanner-text-dim uppercase mb-1">Nearest Fib Resistance</p>
                          <p className="text-scanner-bearish font-mono text-lg font-bold">${analysis.fibonacci.nearest_resistance.toFixed(2)}</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {activeTab === 'signals' && analysis?.signals && (
                  <div className="space-y-3">
                    <div className="flex items-center gap-4 p-4 rounded-xl bg-scanner-card border border-scanner-border mb-4">
                      <div className="text-center">
                        <p className="text-2xl font-bold text-scanner-bullish">{analysis.signal_counts?.bullish || 0}</p>
                        <p className="text-[10px] text-scanner-text-dim uppercase">Bullish</p>
                      </div>
                      <div className="flex-1 h-2 bg-scanner-bg rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-scanner-bullish to-emerald-500 rounded-full"
                          style={{ width: `${((analysis.signal_counts?.bullish || 0) / Math.max((analysis.signal_counts?.bullish || 0) + (analysis.signal_counts?.bearish || 0), 1)) * 100}%` }}
                        />
                      </div>
                      <div className="text-center">
                        <p className="text-2xl font-bold text-scanner-bearish">{analysis.signal_counts?.bearish || 0}</p>
                        <p className="text-[10px] text-scanner-text-dim uppercase">Bearish</p>
                      </div>
                    </div>
                    {analysis.signals.map((signal, idx) => {
                      const isBullish = signal.toLowerCase().includes('bullish') || signal.toLowerCase().includes('oversold') || signal.toLowerCase().includes('golden');
                      return (
                        <div key={idx} className={`flex items-center gap-3 p-3 rounded-lg border ${
                          isBullish ? 'bg-scanner-bullish/5 border-scanner-bullish/20' : 'bg-scanner-bearish/5 border-scanner-bearish/20'
                        }`}>
                          {isBullish ? <TrendingUp size={14} className="text-scanner-bullish flex-shrink-0" /> : <TrendingDown size={14} className="text-scanner-bearish flex-shrink-0" />}
                          <span className="text-sm">{signal}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </>
          )}

          {/* Disclaimer */}
          <div className="px-5 py-3 border-t border-scanner-border bg-scanner-bg/30">
            <p className="text-[10px] text-scanner-text-dim text-center">
              Pattern detection is for research only and does not constitute financial advice.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// Sub-component for indicator cards
function IndicatorCard({ title, value, status, detail }) {
  const statusColors = {
    bullish: 'border-scanner-bullish/30 bg-scanner-bullish/5',
    bearish: 'border-scanner-bearish/30 bg-scanner-bearish/5',
    neutral: 'border-scanner-border bg-scanner-card',
  };
  const dotColors = { bullish: 'bg-scanner-bullish', bearish: 'bg-scanner-bearish', neutral: 'bg-scanner-neutral' };

  return (
    <div className={`p-4 rounded-xl border ${statusColors[status]}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-scanner-text-dim">{title}</span>
        <div className={`w-2 h-2 rounded-full ${dotColors[status]}`} />
      </div>
      <p className="font-mono text-lg font-bold">{value || '—'}</p>
      {detail && <p className="text-[10px] text-scanner-text-dim mt-1">{detail}</p>}
    </div>
  );
}
