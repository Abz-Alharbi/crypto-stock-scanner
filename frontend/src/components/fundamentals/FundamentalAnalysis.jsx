import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Search, Building2, DollarSign, TrendingUp, TrendingDown, BarChart3,
  PieChart, Shield, Coins, FileText, ExternalLink, Loader2, AlertCircle,
  Users, Globe, Calendar, Sparkles
} from 'lucide-react';
import useFundamentalsStore from '../../store/useFundamentalsStore';

// ── Metric Card Component ─────────────────────────────────
function MetricCard({ label, value, subtext, color, icon: Icon }) {
  const displayVal = value === null || value === undefined ? '—' : value;
  return (
    <div className="rounded-lg p-3.5 transition-all hover:scale-[1.02]"
      style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
      <div className="flex items-start justify-between mb-1">
        <span className="text-[10px] uppercase tracking-widest" style={{ color: 'var(--color-text-muted)' }}>{label}</span>
        {Icon && <Icon size={12} style={{ color: color || 'var(--color-text-muted)' }} />}
      </div>
      <div className="font-mono font-bold text-lg" style={{ color: color || 'var(--color-text)' }}>
        {displayVal}
      </div>
      {subtext && <div className="text-[10px] mt-0.5 font-mono" style={{ color: 'var(--color-text-muted)' }}>{subtext}</div>}
    </div>
  );
}

// ── Section Header ────────────────────────────────────────
function SectionHeader({ icon: Icon, title, color }) {
  return (
    <div className="flex items-center gap-2 mb-3 mt-6">
      <div className="w-7 h-7 rounded-lg flex items-center justify-center"
        style={{ background: `color-mix(in srgb, ${color} 12%, transparent)` }}>
        <Icon size={14} style={{ color }} />
      </div>
      <h3 className="font-display font-semibold text-sm" style={{ color: 'var(--color-text)' }}>{title}</h3>
    </div>
  );
}

// ── Metric Bar (visual ratio) ─────────────────────────────
function MetricBar({ label, value, max, unit = '%', color = 'var(--color-accent)' }) {
  if (value === null || value === undefined) return null;
  const pct = Math.min(100, Math.max(0, (Math.abs(value) / max) * 100));
  const isNeg = value < 0;
  return (
    <div className="flex items-center gap-3 py-1.5">
      <span className="text-[11px] w-28 shrink-0" style={{ color: 'var(--color-text-dim)' }}>{label}</span>
      <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: 'var(--color-border)' }}>
        <div className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: isNeg ? 'var(--color-danger)' : color }} />
      </div>
      <span className="font-mono text-xs w-16 text-right" style={{ color: isNeg ? 'var(--color-danger)' : color }}>
        {value}{unit}
      </span>
    </div>
  );
}

// ── Company Header ────────────────────────────────────────
function CompanyHeader({ company }) {
  if (!company) return null;

  return (
    <div className="rounded-xl p-5 mb-4" style={{ background: 'var(--color-card)', border: '1px solid var(--color-border)' }}>
      <div className="flex flex-col sm:flex-row gap-4">
        {/* Logo + Name */}
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {company.logo ? (
            <img src={`${company.logo}?apiKey=${''}`} alt="" className="w-12 h-12 rounded-xl object-contain"
              style={{ background: 'var(--color-surface)' }}
              onError={(e) => { e.target.style.display = 'none'; }} />
          ) : (
            <div className="w-12 h-12 rounded-xl flex items-center justify-center"
              style={{ background: 'var(--color-accent-dim)' }}>
              <Building2 size={24} style={{ color: 'var(--color-accent)' }} />
            </div>
          )}
          <div className="min-w-0">
            <h2 className="font-display font-bold text-xl truncate" style={{ color: 'var(--color-text)' }}>
              {company.name}
            </h2>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono font-bold text-sm" style={{ color: 'var(--color-accent)' }}>{company.ticker}</span>
              {company.exchange && (
                <span className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                  style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)', border: '1px solid var(--color-border)' }}>
                  {company.exchange}
                </span>
              )}
              {company.sector && (
                <span className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                  style={{ background: 'var(--color-accent-dim)', color: 'var(--color-accent)' }}>
                  {company.sector}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Price + Market Cap */}
        <div className="flex gap-6 items-center">
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-widest" style={{ color: 'var(--color-text-muted)' }}>Price</div>
            <div className="font-mono font-bold text-2xl" style={{ color: 'var(--color-text)' }}>
              ${company.current_price?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>
          {company.market_cap_formatted && (
            <div className="text-right">
              <div className="text-[10px] uppercase tracking-widest" style={{ color: 'var(--color-text-muted)' }}>Market Cap</div>
              <div className="font-mono font-bold text-2xl" style={{ color: 'var(--color-accent)' }}>
                {company.market_cap_formatted}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Company Info Row */}
      <div className="flex flex-wrap gap-4 mt-4 pt-3" style={{ borderTop: '1px solid var(--color-border)' }}>
        {company.employees && (
          <div className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--color-text-dim)' }}>
            <Users size={12} /> {company.employees.toLocaleString()} employees
          </div>
        )}
        {company.homepage && (
          <a href={company.homepage} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs transition-colors hover:text-scanner-accent"
            style={{ color: 'var(--color-text-dim)' }}>
            <Globe size={12} /> Website <ExternalLink size={10} />
          </a>
        )}
        {company.list_date && (
          <div className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--color-text-dim)' }}>
            <Calendar size={12} /> Listed {company.list_date}
          </div>
        )}
      </div>

      {/* Description */}
      {company.description && (
        <p className="text-xs leading-relaxed mt-3 line-clamp-3" style={{ color: 'var(--color-text-dim)' }}>
          {company.description}
        </p>
      )}
    </div>
  );
}

// ── Summary Card ──────────────────────────────────────────
function SummaryCard({ summary, lastFiling }) {
  if (!summary) return null;
  return (
    <div className="rounded-xl p-5 mb-6" style={{
      background: `linear-gradient(135deg, color-mix(in srgb, var(--color-accent) 4%, var(--color-card)), var(--color-card))`,
      border: '1px solid color-mix(in srgb, var(--color-accent) 20%, var(--color-border))',
    }}>
      <div className="flex items-center gap-2 mb-3">
        <Sparkles size={16} style={{ color: 'var(--color-accent)' }} />
        <span className="font-display font-semibold text-sm" style={{ color: 'var(--color-text)' }}>Analysis Summary</span>
      </div>
      <p className="text-sm leading-relaxed" style={{ color: 'var(--color-text-dim)' }}>{summary}</p>
      {lastFiling && (
        <div className="flex items-center gap-1.5 mt-3 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
          <FileText size={10} /> Based on filing dated {lastFiling}
        </div>
      )}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────
export default function FundamentalAnalysis() {
  const { symbol } = useParams();
  const navigate = useNavigate();
  const [searchInput, setSearchInput] = useState('');
  const { data, isLoading, error, currentSymbol, fetchFundamentals, reset } = useFundamentalsStore();

  const handleSearch = (e) => {
    e.preventDefault();
    const sym = searchInput.trim().toUpperCase();
    if (sym) navigate(`/fundamentals/${encodeURIComponent(sym)}`);
  };

  useEffect(() => {
    if (!symbol) return;
    const routeSymbol = symbol.trim().toUpperCase();
    setSearchInput(routeSymbol);
    fetchFundamentals(routeSymbol);
  }, [symbol]);

  useEffect(() => () => reset(), []);

  return (
    <div>
      {/* Page Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="font-display text-2xl font-bold flex items-center gap-2">
            <PieChart size={24} className="text-scanner-accent" />
            Fundamental Analysis
          </h2>
          <p className="text-sm mt-1" style={{ color: 'var(--color-text-dim)' }}>
            Company financials, valuation metrics & financial health dashboard
          </p>
        </div>

        <form onSubmit={handleSearch} className="flex items-center gap-2 w-full md:w-auto">
          <div className="relative flex-1 md:w-72">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--color-text-muted)' }} />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value.toUpperCase())}
              placeholder="Enter symbol (AAPL, MSFT...)"
              className="w-full pl-10 pr-4 py-2.5 rounded-xl text-sm font-mono outline-none transition-all"
              style={{ background: 'var(--color-card)', color: 'var(--color-text)', border: '1px solid var(--color-border)' }}
              onFocus={(e) => e.target.style.borderColor = 'var(--color-accent)'}
              onBlur={(e) => e.target.style.borderColor = 'var(--color-border)'}
            />
          </div>
          <button type="submit" disabled={!searchInput.trim() || isLoading}
            className="px-5 py-2.5 rounded-xl text-sm font-semibold transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ background: 'var(--color-accent)', color: 'var(--color-bg)' }}>
            {isLoading ? <Loader2 size={16} className="animate-spin" /> : 'Analyze'}
          </button>
        </form>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 flex items-center gap-3 p-3 rounded-xl text-sm"
          style={{ background: 'color-mix(in srgb, var(--color-danger) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--color-danger) 25%, transparent)', color: 'var(--color-danger)' }}>
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="rounded-2xl p-12 text-center" style={{ background: 'var(--color-card)', border: '1px solid var(--color-border)' }}>
          <Loader2 size={32} className="mx-auto animate-spin mb-3" style={{ color: 'var(--color-accent)' }} />
          <p className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>Fetching financials for {currentSymbol}...</p>
          <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>Retrieving income statement, balance sheet & cash flows</p>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !data && !error && (
        <div className="rounded-2xl p-12 text-center" style={{ background: 'var(--color-card)', border: '1px solid var(--color-border)' }}>
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center" style={{ background: 'var(--color-accent-dim)' }}>
            <PieChart size={28} style={{ color: 'var(--color-accent)' }} />
          </div>
          <h3 className="font-display text-xl font-bold" style={{ color: 'var(--color-text)' }}>Search for a Stock</h3>
          <p className="text-sm mt-2 max-w-md mx-auto" style={{ color: 'var(--color-text-dim)' }}>
            Enter a US stock symbol above to view comprehensive financial metrics, valuation ratios, and health indicators.
          </p>
          <div className="flex flex-wrap justify-center gap-2 mt-4">
            {['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META'].map((sym) => (
              <button key={sym}
                onClick={() => navigate(`/fundamentals/${sym}`)}
                className="px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all hover:scale-105"
                style={{ background: 'var(--color-surface)', color: 'var(--color-accent)', border: '1px solid var(--color-border)' }}>
                {sym}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Results Dashboard */}
      {!isLoading && data && (
        <div className="animate-fade-in">
          <CompanyHeader company={data.company} />
          <SummaryCard summary={data.summary} lastFiling={data.last_filing} />

          {/* ── Valuation Metrics ─────────────────────── */}
          <SectionHeader icon={DollarSign} title="Valuation Metrics" color="var(--color-accent)" />
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <MetricCard label="P/E Ratio" value={data.valuation?.pe_ratio} icon={BarChart3} />
            <MetricCard label="Forward P/E" value={data.valuation?.forward_pe} icon={BarChart3} />
            <MetricCard label="PEG Ratio" value={data.valuation?.peg_ratio} icon={TrendingUp} />
            <MetricCard label="P/B Ratio" value={data.valuation?.pb_ratio} icon={BarChart3} />
            <MetricCard label="P/S Ratio" value={data.valuation?.ps_ratio} icon={BarChart3} />
            <MetricCard label="EV/EBITDA" value={data.valuation?.ev_ebitda} icon={BarChart3} />
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
            <MetricCard label="EPS (Basic)" value={data.valuation?.eps_basic ? `$${data.valuation.eps_basic}` : null} icon={DollarSign} />
            <MetricCard label="EPS (Diluted)" value={data.valuation?.eps_diluted ? `$${data.valuation.eps_diluted}` : null} icon={DollarSign} />
            <MetricCard label="Enterprise Value" value={data.valuation?.enterprise_value_formatted} icon={Building2} />
            <MetricCard label="Market Cap" value={data.company?.market_cap_formatted} color="var(--color-accent)" icon={DollarSign} />
          </div>

          {/* ── Profitability ────────────────────────── */}
          <SectionHeader icon={TrendingUp} title="Profitability" color="var(--color-bullish)" />
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            <MetricCard label="Revenue" value={data.profitability?.revenue_formatted} color="var(--color-accent)" icon={BarChart3} />
            <MetricCard label="Net Income" value={data.profitability?.net_income_formatted}
              color={data.profitability?.net_income >= 0 ? 'var(--color-bullish)' : 'var(--color-bearish)'} icon={DollarSign} />
            <MetricCard label="Gross Profit" value={data.profitability?.gross_profit_formatted} icon={DollarSign} />
            <MetricCard label="Operating Income" value={data.profitability?.operating_income_formatted} icon={DollarSign} />
          </div>

          {/* Margin Bars */}
          <div className="rounded-xl p-4 mt-3" style={{ background: 'var(--color-card)', border: '1px solid var(--color-border)' }}>
            <div className="text-[10px] uppercase tracking-widest mb-3" style={{ color: 'var(--color-text-muted)' }}>Margins & Returns</div>
            <MetricBar label="Gross Margin" value={data.profitability?.gross_margin} max={80} color="var(--color-accent)" />
            <MetricBar label="Operating Margin" value={data.profitability?.operating_margin} max={60} color="var(--color-bullish)" />
            <MetricBar label="Profit Margin" value={data.profitability?.profit_margin} max={50} color="var(--color-bullish)" />
            <MetricBar label="ROE" value={data.profitability?.roe} max={60} color="var(--color-accent)" />
            <MetricBar label="ROA" value={data.profitability?.roa} max={30} color="var(--color-accent)" />
          </div>

          {/* ── Growth ───────────────────────────────── */}
          <SectionHeader icon={TrendingUp} title="Growth" color="#f59e0b" />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <MetricCard label="Revenue Growth" icon={TrendingUp}
              value={data.growth?.revenue_growth != null ? `${data.growth.revenue_growth}%` : null}
              color={data.growth?.revenue_growth >= 0 ? 'var(--color-bullish)' : 'var(--color-bearish)'}
              subtext="Year-over-year" />
            <MetricCard label="Earnings Growth" icon={TrendingUp}
              value={data.growth?.earnings_growth != null ? `${data.growth.earnings_growth}%` : null}
              color={data.growth?.earnings_growth >= 0 ? 'var(--color-bullish)' : 'var(--color-bearish)'}
              subtext="Year-over-year" />
            <MetricCard label="Fiscal Year" value={data.growth?.fiscal_year} icon={Calendar} subtext={data.growth?.fiscal_period} />
            <MetricCard label="Last Filing" value={data.last_filing} icon={FileText} />
          </div>

          {/* ── Financial Health ──────────────────────── */}
          <SectionHeader icon={Shield} title="Financial Health" color="#6366f1" />
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            <MetricCard label="Total Assets" value={data.health?.total_assets_formatted} icon={BarChart3} />
            <MetricCard label="Total Liabilities" value={data.health?.total_liabilities_formatted} icon={BarChart3}
              color="var(--color-warning)" />
            <MetricCard label="Total Equity" value={data.health?.total_equity_formatted} icon={BarChart3}
              color="var(--color-bullish)" />
            <MetricCard label="Debt-to-Equity"
              value={data.health?.debt_to_equity}
              color={data.health?.debt_to_equity > 1.5 ? 'var(--color-danger)' : data.health?.debt_to_equity > 0.8 ? 'var(--color-warning)' : 'var(--color-bullish)'}
              icon={Shield} />
            <MetricCard label="Current Ratio"
              value={data.health?.current_ratio}
              color={data.health?.current_ratio >= 1.5 ? 'var(--color-bullish)' : data.health?.current_ratio >= 1 ? 'var(--color-warning)' : 'var(--color-danger)'}
              icon={Shield}
              subtext={data.health?.current_ratio >= 1.5 ? 'Healthy' : data.health?.current_ratio >= 1 ? 'Adequate' : 'Low'} />
            <MetricCard label="Book Value/Share"
              value={data.health?.book_value_per_share ? `$${data.health.book_value_per_share}` : null}
              icon={DollarSign} />
            <MetricCard label="Free Cash Flow" value={data.health?.free_cash_flow_formatted}
              color={data.health?.free_cash_flow >= 0 ? 'var(--color-bullish)' : 'var(--color-danger)'}
              icon={DollarSign} />
            <MetricCard label="Operating Cash Flow" value={data.health?.operating_cash_flow_formatted} icon={DollarSign} />
          </div>

          {/* Balance Sheet Visual */}
          {data.health?.total_assets > 0 && (
            <div className="rounded-xl p-4 mt-3" style={{ background: 'var(--color-card)', border: '1px solid var(--color-border)' }}>
              <div className="text-[10px] uppercase tracking-widest mb-3" style={{ color: 'var(--color-text-muted)' }}>
                Assets vs. Liabilities
              </div>
              <div className="flex h-6 rounded-lg overflow-hidden">
                <div className="flex items-center justify-center text-[10px] font-mono font-bold text-white"
                  style={{
                    width: `${(data.health.total_equity / data.health.total_assets) * 100}%`,
                    background: 'var(--color-bullish)', minWidth: '30px',
                  }}>
                  Equity {((data.health.total_equity / data.health.total_assets) * 100).toFixed(0)}%
                </div>
                <div className="flex items-center justify-center text-[10px] font-mono font-bold text-white"
                  style={{
                    width: `${(data.health.total_liabilities / data.health.total_assets) * 100}%`,
                    background: 'var(--color-warning)', minWidth: '30px',
                  }}>
                  Liabilities {((data.health.total_liabilities / data.health.total_assets) * 100).toFixed(0)}%
                </div>
              </div>
            </div>
          )}

          {/* ── Dividends ────────────────────────────── */}
          <SectionHeader icon={Coins} title="Dividends" color="#f59e0b" />
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <MetricCard label="Dividend Yield"
              value={data.dividends?.dividend_yield != null ? `${data.dividends.dividend_yield}%` : 'None'}
              color={data.dividends?.dividend_yield > 0 ? 'var(--color-warning)' : 'var(--color-text-muted)'}
              icon={Coins} />
            <MetricCard label="Annual Dividend"
              value={data.dividends?.annual_dividend ? `$${data.dividends.annual_dividend}` : 'N/A'}
              icon={DollarSign} />
            <MetricCard label="Div Per Share"
              value={data.dividends?.dividend_per_share ? `$${data.dividends.dividend_per_share}` : 'N/A'}
              icon={DollarSign} />
            <MetricCard label="Frequency" value={data.dividends?.frequency || 'N/A'} icon={Calendar} />
            <MetricCard label="Ex-Div Date" value={data.dividends?.ex_dividend_date || 'N/A'} icon={Calendar} />
            <MetricCard label="Payout Ratio"
              value={data.dividends?.payout_ratio != null ? `${data.dividends.payout_ratio}%` : 'N/A'}
              color={data.dividends?.payout_ratio > 80 ? 'var(--color-danger)' : data.dividends?.payout_ratio > 50 ? 'var(--color-warning)' : 'var(--color-bullish)'}
              icon={PieChart} />
          </div>

          {/* Disclaimer */}
          <div className="mt-6 px-4 py-3 rounded-lg text-[11px] leading-relaxed"
            style={{
              background: 'color-mix(in srgb, var(--color-warning) 5%, transparent)',
              border: '1px solid color-mix(in srgb, var(--color-warning) 15%, transparent)',
              color: 'color-mix(in srgb, var(--color-warning) 70%, var(--color-text-dim))',
            }}>
            ⚠️ Financial data sourced from Polygon.io. Figures may be delayed or based on most recent SEC filings.
            This is for educational purposes only and should not be considered investment advice.
            Always verify data with official filings before making investment decisions.
          </div>
        </div>
      )}
    </div>
  );
}
