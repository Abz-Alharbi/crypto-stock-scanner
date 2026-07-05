import React, { useState, useEffect } from 'react';
import {
  Newspaper, Search, TrendingUp, TrendingDown, Minus, ExternalLink,
  Filter, X, Clock, BarChart3, AlertCircle, Loader2, Sparkles, Rss, Globe
} from 'lucide-react';
import useNewsStore from '../../store/useNewsStore';
import useMarketStore from '../../store/useMarketStore';

// ── Sentiment helpers ─────────────────────────────────────
const SENTIMENT_CONFIG = {
  positive: { color: 'var(--color-bullish)', label: 'Positive', icon: TrendingUp, emoji: '🟢' },
  negative: { color: 'var(--color-bearish)', label: 'Negative', icon: TrendingDown, emoji: '🔴' },
  neutral:  { color: 'var(--color-neutral)', label: 'Neutral', icon: Minus, emoji: '⚪' },
};

const FEED_LABELS = {
  polygon: 'Polygon.io',
  finnhub: 'Finnhub',
  alpha_vantage: 'Alpha Vantage',
  google_rss: 'Google News',
  yahoo_rss: 'Yahoo Finance',
  marketwatch_rss: 'MarketWatch',
};

function SentimentBadge({ sentiment, score, size = 'sm' }) {
  const cfg = SENTIMENT_CONFIG[sentiment] || SENTIMENT_CONFIG.neutral;
  const Icon = cfg.icon;
  const isLg = size === 'lg';

  return (
    <span
      className={`inline-flex items-center gap-1 font-semibold uppercase tracking-wide rounded-full ${isLg ? 'px-3 py-1.5 text-xs' : 'px-2 py-0.5 text-[10px]'}`}
      style={{
        color: cfg.color,
        background: `color-mix(in srgb, ${cfg.color} 10%, transparent)`,
        border: `1px solid color-mix(in srgb, ${cfg.color} 25%, transparent)`,
      }}
    >
      <Icon size={isLg ? 14 : 10} />
      {cfg.label}
      {score != null && <span className="font-mono opacity-70 ml-0.5">{(score * 100).toFixed(0)}%</span>}
    </span>
  );
}

// ── Active Feeds Indicator ────────────────────────────────
function ActiveFeeds({ feeds }) {
  if (!feeds || feeds.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5 mb-4">
      <div className="flex items-center gap-1 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
        <Rss size={10} /> Sources:
      </div>
      {feeds.map((feed) => (
        <span key={feed} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium"
          style={{ background: 'var(--color-surface)', color: 'var(--color-text-dim)', border: '1px solid var(--color-border)' }}>
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--color-bullish)' }} />
          {FEED_LABELS[feed] || feed}
        </span>
      ))}
    </div>
  );
}

// ── Sentiment Summary Bar ─────────────────────────────────
function SentimentSummary({ summary, sentimentEngine }) {
  if (!summary || summary.total === 0) return null;

  const { positive_count, negative_count, neutral_count, total, overall } = summary;
  const posW = (positive_count / total) * 100;
  const negW = (negative_count / total) * 100;
  const neuW = (neutral_count / total) * 100;
  const cfg = SENTIMENT_CONFIG[overall] || SENTIMENT_CONFIG.neutral;

  return (
    <div className="rounded-xl p-5 mb-6" style={{ background: 'var(--color-card)', border: '1px solid var(--color-border)' }}>
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center"
            style={{ background: `color-mix(in srgb, ${cfg.color} 12%, transparent)` }}>
            <BarChart3 size={20} style={{ color: cfg.color }} />
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-widest" style={{ color: 'var(--color-text-muted)' }}>Overall Sentiment</div>
            <SentimentBadge sentiment={overall} size="lg" />
          </div>
        </div>
        <div className="flex items-center gap-4 text-xs font-mono">
          <span style={{ color: 'var(--color-bullish)' }}>🟢 {positive_count} positive</span>
          <span style={{ color: 'var(--color-neutral)' }}>⚪ {neutral_count} neutral</span>
          <span style={{ color: 'var(--color-bearish)' }}>🔴 {negative_count} negative</span>
        </div>
      </div>

      {/* Sentiment distribution bar */}
      <div className="flex h-3 rounded-full overflow-hidden" style={{ background: 'var(--color-border)' }}>
        {posW > 0 && <div style={{ width: `${posW}%`, background: 'var(--color-bullish)' }} title={`Positive: ${positive_count}`} />}
        {neuW > 0 && <div style={{ width: `${neuW}%`, background: 'var(--color-neutral)' }} title={`Neutral: ${neutral_count}`} />}
        {negW > 0 && <div style={{ width: `${negW}%`, background: 'var(--color-bearish)' }} title={`Negative: ${negative_count}`} />}
      </div>

      <div className="flex items-center gap-2 mt-3 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
        <Sparkles size={10} />
        Powered by {sentimentEngine === 'finbert' ? 'FinBERT AI Model' : 'Financial Lexicon Engine'}
        <span className="mx-1">•</span>
        {total} articles analyzed from multiple sources
      </div>
    </div>
  );
}

// ── News Card ─────────────────────────────────────────────
function NewsCard({ article }) {
  const timeAgo = (dateStr) => {
    try {
      const d = new Date(dateStr);
      const now = new Date();
      const diff = Math.floor((now - d) / 1000);
      if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
      if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
      if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
      return d.toLocaleDateString();
    } catch { return dateStr; }
  };

  const feedLabel = FEED_LABELS[article.news_source] || '';

  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block rounded-xl transition-all duration-200 hover:-translate-y-0.5 group"
      style={{
        background: 'var(--color-card)',
        border: '1px solid var(--color-border)',
        boxShadow: 'var(--shadow-sm)',
      }}
    >
      {/* Image */}
      {article.image_url && (
        <div className="h-40 overflow-hidden rounded-t-xl">
          <img
            src={article.image_url}
            alt=""
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
            onError={(e) => { e.target.style.display = 'none'; }}
          />
        </div>
      )}

      <div className="p-4">
        {/* Header: source + date + sentiment */}
        <div className="flex items-center justify-between gap-2 mb-2">
          <div className="flex items-center gap-2 text-[11px] min-w-0">
            {article.source_logo && (
              <img src={article.source_logo} alt="" className="w-4 h-4 rounded" onError={(e) => { e.target.style.display = 'none'; }} />
            )}
            <span className="font-medium truncate" style={{ color: 'var(--color-text-dim)' }}>{article.source}</span>
            <span style={{ color: 'var(--color-text-muted)' }}>•</span>
            <span className="flex items-center gap-1 whitespace-nowrap" style={{ color: 'var(--color-text-muted)' }}>
              <Clock size={10} /> {timeAgo(article.date)}
            </span>
          </div>
          <SentimentBadge sentiment={article.sentiment} score={article.sentiment_score} />
        </div>

        {/* Headline */}
        <h3 className="font-display font-semibold text-sm leading-snug mb-2 group-hover:text-scanner-accent transition-colors line-clamp-2"
          style={{ color: 'var(--color-text)' }}>
          {article.headline}
        </h3>

        {/* Summary */}
        <p className="text-xs leading-relaxed mb-3 line-clamp-3" style={{ color: 'var(--color-text-dim)' }}>
          {article.summary}
        </p>

        {/* Footer: tickers + feed origin + link */}
        <div className="flex items-center justify-between">
          <div className="flex flex-wrap items-center gap-1">
            {article.tickers?.slice(0, 4).map((t, i) => (
              <span key={i} className="text-[9px] px-1.5 py-0.5 rounded font-mono font-medium"
                style={{ background: 'var(--color-accent-dim)', color: 'var(--color-accent)' }}>
                {t}
              </span>
            ))}
            {feedLabel && (
              <span className="text-[9px] px-1.5 py-0.5 rounded font-medium"
                style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)', border: '1px solid var(--color-border)' }}>
                via {feedLabel}
              </span>
            )}
          </div>
          <span className="flex items-center gap-1 text-[10px] transition-colors group-hover:text-scanner-accent"
            style={{ color: 'var(--color-text-muted)' }}>
            Read more <ExternalLink size={10} />
          </span>
        </div>
      </div>
    </a>
  );
}

// ── Filter Bar ────────────────────────────────────────────
function FilterBar({ sources }) {
  const { sentimentFilter, sourceFilter, daysFilter, setSentimentFilter, setSourceFilter, setDaysFilter, clearFilters } = useNewsStore();
  const hasFilters = sentimentFilter || sourceFilter || daysFilter !== 30;

  return (
    <div className="flex flex-wrap items-center gap-2 mb-4">
      <Filter size={14} style={{ color: 'var(--color-text-muted)' }} />

      {/* Sentiment filter */}
      {['positive', 'neutral', 'negative'].map((s) => {
        const cfg = SENTIMENT_CONFIG[s];
        const active = sentimentFilter === s;
        return (
          <button
            key={s}
            onClick={() => setSentimentFilter(active ? null : s)}
            className="px-2.5 py-1 rounded-lg text-[11px] font-semibold transition-all"
            style={{
              background: active ? `color-mix(in srgb, ${cfg.color} 15%, transparent)` : 'var(--color-surface)',
              color: active ? cfg.color : 'var(--color-text-dim)',
              border: `1px solid ${active ? `color-mix(in srgb, ${cfg.color} 30%, transparent)` : 'var(--color-border)'}`,
            }}
          >
            {cfg.emoji} {cfg.label}
          </button>
        );
      })}

      <span className="mx-1" style={{ color: 'var(--color-border)' }}>|</span>

      {/* Source filter */}
      <select
        value={sourceFilter || ''}
        onChange={(e) => setSourceFilter(e.target.value || null)}
        className="px-2.5 py-1 rounded-lg text-[11px] font-medium outline-none cursor-pointer"
        style={{ background: 'var(--color-surface)', color: 'var(--color-text-dim)', border: '1px solid var(--color-border)' }}
      >
        <option value="">All Sources</option>
        {sources.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>

      {/* Days filter */}
      <select
        value={daysFilter}
        onChange={(e) => setDaysFilter(Number(e.target.value))}
        className="px-2.5 py-1 rounded-lg text-[11px] font-medium outline-none cursor-pointer"
        style={{ background: 'var(--color-surface)', color: 'var(--color-text-dim)', border: '1px solid var(--color-border)' }}
      >
        <option value={7}>Last 7 days</option>
        <option value={14}>Last 14 days</option>
        <option value={30}>Last 30 days</option>
      </select>

      {/* Clear */}
      {hasFilters && (
        <button onClick={clearFilters} className="flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] transition-colors"
          style={{ color: 'var(--color-danger)', background: 'color-mix(in srgb, var(--color-danger) 8%, transparent)' }}>
          <X size={10} /> Clear
        </button>
      )}
    </div>
  );
}

// ── Main NewsRoom Component ───────────────────────────────
export default function NewsRoom() {
  const [searchInput, setSearchInput] = useState('');
  const { articles, summary, sources, activeFeeds, sentimentEngine, total, isLoading, error, currentSymbol, fetchNews, reset } = useNewsStore();
  const { activeMarket } = useMarketStore();

  const handleSearch = (e) => {
    e.preventDefault();
    const sym = searchInput.trim().toUpperCase();
    if (sym) fetchNews(sym);
  };

  // Reset on unmount
  useEffect(() => () => reset(), []);

  return (
    <div>
      {/* Page Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="font-display text-2xl font-bold flex items-center gap-2">
            <Newspaper size={24} className="text-scanner-accent" />
            Newsroom
          </h2>
          <p className="text-sm mt-1" style={{ color: 'var(--color-text-dim)' }}>
            Multi-source news aggregator with AI sentiment analysis
          </p>
        </div>

        {/* Search */}
        <form onSubmit={handleSearch} className="flex items-center gap-2 w-full md:w-auto">
          <div className="relative flex-1 md:w-72">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--color-text-muted)' }} />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value.toUpperCase())}
              placeholder="Enter symbol (AAPL, TSLA, BTC...)"
              className="w-full pl-10 pr-4 py-2.5 rounded-xl text-sm font-mono outline-none transition-all"
              style={{
                background: 'var(--color-card)',
                color: 'var(--color-text)',
                border: '1px solid var(--color-border)',
              }}
              onFocus={(e) => e.target.style.borderColor = 'var(--color-accent)'}
              onBlur={(e) => e.target.style.borderColor = 'var(--color-border)'}
            />
          </div>
          <button
            type="submit"
            disabled={!searchInput.trim() || isLoading}
            className="px-5 py-2.5 rounded-xl text-sm font-semibold transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              background: 'var(--color-accent)',
              color: 'var(--color-bg)',
            }}
          >
            {isLoading ? <Loader2 size={16} className="animate-spin" /> : 'Analyze'}
          </button>
        </form>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 flex items-center gap-3 p-3 rounded-xl text-sm animate-fade-in"
          style={{ background: 'color-mix(in srgb, var(--color-danger) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--color-danger) 25%, transparent)', color: 'var(--color-danger)' }}>
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="rounded-2xl p-12 text-center" style={{ background: 'var(--color-card)', border: '1px solid var(--color-border)' }}>
          <Loader2 size={32} className="mx-auto animate-spin mb-3" style={{ color: 'var(--color-accent)' }} />
          <p className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>Fetching news for {currentSymbol}...</p>
          <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
            Searching Polygon.io, Yahoo Finance, Google News & more
          </p>
          <div className="flex justify-center gap-2 mt-3">
            {['Polygon', 'Yahoo', 'Google News', 'Finnhub'].map((s) => (
              <span key={s} className="text-[10px] px-2 py-0.5 rounded-md animate-pulse"
                style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)', border: '1px solid var(--color-border)' }}>
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !currentSymbol && (
        <div className="rounded-2xl p-12 text-center" style={{ background: 'var(--color-card)', border: '1px solid var(--color-border)' }}>
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center"
            style={{ background: 'var(--color-accent-dim)' }}>
            <Newspaper size={28} style={{ color: 'var(--color-accent)' }} />
          </div>
          <h3 className="font-display text-xl font-bold" style={{ color: 'var(--color-text)' }}>Search for a Symbol</h3>
          <p className="text-sm mt-2 max-w-md mx-auto" style={{ color: 'var(--color-text-dim)' }}>
            Enter a stock or crypto symbol above to fetch news from multiple sources with sentiment analysis.
          </p>
          {/* Source logos */}
          <div className="flex justify-center items-center gap-3 mt-4 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
            <Globe size={12} />
            Polygon.io • Yahoo Finance • Google News • Finnhub • Alpha Vantage • MarketWatch
          </div>
          <div className="flex flex-wrap justify-center gap-2 mt-4">
            {['AAPL', 'TSLA', 'NVDA', 'MSFT', 'AMZN', 'GOOGL'].map((sym) => (
              <button
                key={sym}
                onClick={() => { setSearchInput(sym); fetchNews(sym); }}
                className="px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all hover:scale-105"
                style={{
                  background: 'var(--color-surface)',
                  color: 'var(--color-accent)',
                  border: '1px solid var(--color-border)',
                }}
              >
                {sym}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Results */}
      {!isLoading && currentSymbol && (
        <>
          {/* Symbol header */}
          <div className="flex items-center gap-2 mb-4">
            <h3 className="font-mono font-bold text-lg" style={{ color: 'var(--color-accent)' }}>{currentSymbol}</h3>
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>— {total} article{total !== 1 ? 's' : ''}</span>
          </div>

          {/* Active feeds */}
          <ActiveFeeds feeds={activeFeeds} />

          {/* Sentiment Summary */}
          <SentimentSummary summary={summary} sentimentEngine={sentimentEngine} />

          {/* Filters */}
          <FilterBar sources={sources} />

          {/* No results after filter */}
          {articles.length === 0 ? (
            <div className="rounded-xl p-8 text-center" style={{ background: 'var(--color-card)', border: '1px solid var(--color-border)' }}>
              <Newspaper size={32} className="mx-auto mb-2" style={{ color: 'var(--color-text-muted)' }} />
              <p className="text-sm" style={{ color: 'var(--color-text-dim)' }}>No news found matching current filters.</p>
            </div>
          ) : (
            /* News Grid */
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {articles.map((article, idx) => (
                <div key={idx} className="animate-fade-in" style={{ animationDelay: `${idx * 40}ms` }}>
                  <NewsCard article={article} />
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
