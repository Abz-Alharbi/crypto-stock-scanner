import { useState } from 'react';

const DIRECTION_CONFIG = {
  long: { label: 'LONG', color: 'var(--color-bullish)', icon: '↗' },
  short: { label: 'SHORT', color: 'var(--color-bearish)', icon: '↘' },
  neutral: { label: 'HOLD', color: 'var(--color-neutral)', icon: '→' },
};

function ConfidenceMeter({ value }) {
  const v = Math.max(0, Math.min(100, value));
  const color = v >= 75 ? 'var(--color-bullish)' : v >= 55 ? 'var(--color-warning)' : 'var(--color-danger)';
  return (
    <div className="flex items-center gap-2">
      <div className="w-full h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--color-border)' }}>
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${v}%`, background: color }} />
      </div>
      <span className="font-mono text-xs font-semibold min-w-[36px]" style={{ color }}>{v}%</span>
    </div>
  );
}

export default function TradeSetupCard({ trade_setup, symbol, compact = false }) {
  const [expanded, setExpanded] = useState(false);

  if (!trade_setup) {
    return (
      <div className="rounded-lg p-3 text-sm" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}>
        No trade setup data available
      </div>
    );
  }

  const ts = trade_setup;
  const dir = DIRECTION_CONFIG[ts.direction] || DIRECTION_CONFIG.neutral;

  if (compact) {
    return (
      <div onClick={() => setExpanded(!expanded)} className="cursor-pointer">
        <div className="flex items-center gap-2.5 flex-wrap">
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-mono font-bold tracking-wide"
            style={{ background: `color-mix(in srgb, ${dir.color} 12%, transparent)`, color: dir.color, border: `1px solid color-mix(in srgb, ${dir.color} 25%, transparent)` }}>
            {dir.icon} {ts.action}
          </span>
          <span className="text-xs" style={{ color: 'var(--color-text-dim)' }}>
            TP: <span className="font-mono" style={{ color: 'var(--color-bullish)' }}>${ts.targets?.t1?.price}</span>
          </span>
          <span className="text-xs" style={{ color: 'var(--color-text-dim)' }}>
            SL: <span className="font-mono" style={{ color: 'var(--color-bearish)' }}>${ts.stop_loss}</span>
          </span>
          <span className="text-[11px] px-1.5 py-0.5 rounded font-mono font-semibold"
            style={{
              background: `color-mix(in srgb, ${ts.risk_reward >= 2 ? 'var(--color-bullish)' : ts.risk_reward >= 1.5 ? 'var(--color-warning)' : 'var(--color-danger)'} 10%, transparent)`,
              color: ts.risk_reward >= 2 ? 'var(--color-bullish)' : ts.risk_reward >= 1.5 ? 'var(--color-warning)' : 'var(--color-danger)',
            }}>
            R:R {ts.risk_reward}:1
          </span>
          <span className="text-[11px] font-mono" style={{ color: ts.confidence >= 70 ? 'var(--color-bullish)' : ts.confidence >= 55 ? 'var(--color-warning)' : 'var(--color-danger)' }}>
            {ts.confidence}%
          </span>
          <span className="text-[10px] ml-auto" style={{ color: 'var(--color-text-muted)' }}>{expanded ? '▲ Less' : '▼ More'}</span>
        </div>
        {expanded && <div className="mt-3"><TradeSetupBody ts={ts} dir={dir} /></div>}
      </div>
    );
  }

  return (
    <div className="rounded-xl p-5 w-full" style={{ background: 'var(--color-card)', border: '1px solid var(--color-border)' }}>
      <div className="flex justify-between items-center mb-4 pb-3" style={{ borderBottom: '1px solid var(--color-border)' }}>
        <div className="flex items-center gap-2.5">
          <span className="text-sm font-mono font-bold" style={{ color: 'var(--color-text)' }}>{symbol} Trade Setup</span>
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-md text-xs font-mono font-bold tracking-wide"
            style={{ background: `color-mix(in srgb, ${dir.color} 12%, transparent)`, color: dir.color, border: `1px solid color-mix(in srgb, ${dir.color} 30%, transparent)` }}>
            {dir.icon} {ts.action}
          </span>
        </div>
        <div className="text-right">
          <div className="text-[10px] mb-1" style={{ color: 'var(--color-text-muted)' }}>CONFIDENCE</div>
          <ConfidenceMeter value={ts.confidence} />
        </div>
      </div>
      <TradeSetupBody ts={ts} dir={dir} />
    </div>
  );
}

function PriceBox({ label, price, subtitle, color, borderColor }) {
  return (
    <div className="rounded-lg p-3" style={{ background: `color-mix(in srgb, ${color} 5%, var(--color-surface))`, border: `1px solid color-mix(in srgb, ${color} 18%, transparent)` }}>
      <div className="text-[10px] tracking-wide mb-1" style={{ color }}>{label}</div>
      <div className="text-lg font-mono font-bold" style={{ color }}>
        ${price?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </div>
      {subtitle && <div className="text-[11px] font-mono mt-0.5" style={{ color: `color-mix(in srgb, ${color} 70%, var(--color-text-dim))` }}>{subtitle}</div>}
    </div>
  );
}

function TradeSetupBody({ ts, dir }) {
  return (
    <div>
      {/* Price Grid */}
      <div className="grid gap-3 mb-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))' }}>
        <PriceBox label="ENTRY PRICE" price={ts.entry_price} color="var(--color-text)" />
        <PriceBox label="⛔ STOP LOSS" price={ts.stop_loss} subtitle={`Risk: -${ts.potential_loss_pct}%`} color="var(--color-danger)" />
        <PriceBox label={`🎯 TARGET 1 (${ts.targets?.t1?.label})`} price={ts.targets?.t1?.price} subtitle={`+${ts.potential_gain_pct}% · R:R ${ts.targets?.t1?.rr}:1`} color="var(--color-bullish)" />
        <PriceBox label={`🎯 TARGET 2 (${ts.targets?.t2?.label})`} price={ts.targets?.t2?.price} subtitle={`R:R ${ts.targets?.t2?.rr}:1`} color="var(--color-bullish)" />
        <PriceBox label={`🚀 TARGET 3 (${ts.targets?.t3?.label})`} price={ts.targets?.t3?.price} subtitle={`R:R ${ts.targets?.t3?.rr}:1`} color="var(--color-bullish)" />
      </div>

      {/* Risk/Reward Bar */}
      <div className="rounded-lg p-3 mb-4" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
        <div className="text-[10px] tracking-wide mb-2" style={{ color: 'var(--color-text-muted)' }}>RISK / REWARD VISUAL</div>
        <div className="flex h-6 rounded overflow-hidden">
          <div className="flex items-center justify-center text-[10px] font-mono font-bold text-white min-w-[40px]"
            style={{ width: `${Math.min(50, (ts.potential_loss_pct / (ts.potential_loss_pct + ts.potential_gain_pct)) * 100)}%`, background: 'linear-gradient(90deg, var(--color-danger), #dc2626)' }}>
            -{ts.potential_loss_pct}%
          </div>
          <div className="flex-1 flex items-center justify-center text-[10px] font-mono font-bold text-white"
            style={{ background: 'linear-gradient(90deg, var(--color-bullish), #059669)' }}>
            +{ts.potential_gain_pct}%
          </div>
        </div>
      </div>

      {/* Support & Resistance */}
      <div className="grid grid-cols-2 gap-3">
        <LevelList title="SUPPORT LEVELS" levels={ts.support_levels} color="var(--color-bullish)" />
        <LevelList title="RESISTANCE LEVELS" levels={ts.resistance_levels} color="var(--color-danger)" />
      </div>

      {/* ATR Info */}
      <div className="flex gap-4 mt-3 px-3 py-2 rounded-md text-[11px]" style={{ background: 'var(--color-surface)' }}>
        <span style={{ color: 'var(--color-text-muted)' }}>ATR: <span className="font-mono" style={{ color: 'var(--color-text-dim)' }}>${ts.atr}</span></span>
        <span style={{ color: 'var(--color-text-muted)' }}>ATR%: <span className="font-mono" style={{ color: 'var(--color-text-dim)' }}>{ts.atr_pct}%</span></span>
        <span style={{ color: 'var(--color-text-muted)' }}>Direction: <span className="font-mono" style={{ color: dir.color }}>{dir.label}</span></span>
      </div>

      {/* Fibonacci Position */}
      {ts.fib_position && ts.fib_position.zone && (
        <div className="mt-3 rounded-lg p-3" style={{ background: 'color-mix(in srgb, var(--color-accent) 4%, var(--color-surface))', border: '1px solid color-mix(in srgb, var(--color-accent) 15%, var(--color-border))' }}>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[10px] uppercase tracking-widest" style={{ color: 'var(--color-accent)' }}>Fibonacci Position</span>
            {ts.fib_position.trend && (
              <span className="text-[9px] px-1.5 py-0.5 rounded font-mono"
                style={{
                  background: ts.fib_position.trend === 'uptrend' ? 'color-mix(in srgb, var(--color-bullish) 12%, transparent)' : 'color-mix(in srgb, var(--color-bearish) 12%, transparent)',
                  color: ts.fib_position.trend === 'uptrend' ? 'var(--color-bullish)' : 'var(--color-bearish)',
                }}>
                {ts.fib_position.trend === 'uptrend' ? '▲ Uptrend' : '▼ Downtrend'}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            {ts.fib_position.retracement_pct != null && (
              <span className="font-mono font-bold text-sm" style={{ color: 'var(--color-accent)' }}>
                {ts.fib_position.retracement_pct}%
              </span>
            )}
            <span className="text-xs leading-snug" style={{ color: 'var(--color-text-dim)' }}>
              {ts.fib_position.zone_desc || ts.fib_position.zone.replace(/_/g, ' ')}
            </span>
          </div>
          {/* Fib retrace visual bar */}
          {ts.fib_position.retracement_pct != null && (
            <div className="mt-2">
              <div className="flex justify-between text-[9px] font-mono mb-0.5" style={{ color: 'var(--color-text-muted)' }}>
                <span>0%</span>
                <span>23.6</span>
                <span>38.2</span>
                <span className="font-bold" style={{ color: 'var(--color-accent)' }}>50</span>
                <span className="font-bold" style={{ color: 'var(--color-accent)' }}>61.8</span>
                <span>78.6</span>
                <span>100%</span>
              </div>
              <div className="h-2 rounded-full overflow-hidden relative" style={{ background: 'var(--color-border)' }}>
                {/* Golden zone highlight */}
                <div className="absolute h-full opacity-20" style={{ left: '50%', width: '11.8%', background: 'var(--color-accent)' }} />
                {/* Price marker */}
                <div className="absolute h-full w-1 rounded-full" style={{
                  left: `${Math.min(100, Math.max(0, ts.fib_position.retracement_pct))}%`,
                  background: 'var(--color-accent)',
                  boxShadow: '0 0 6px var(--color-accent)',
                  transform: 'translateX(-50%)',
                }} />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Disclaimer */}
      <div className="mt-3 px-3 py-2 rounded text-[10px] leading-relaxed"
        style={{ background: 'color-mix(in srgb, var(--color-warning) 6%, transparent)', border: '1px solid color-mix(in srgb, var(--color-warning) 15%, transparent)', color: 'color-mix(in srgb, var(--color-warning) 70%, var(--color-text-dim))' }}>
        Pattern detection is for research only and does not constitute financial advice.
      </div>
    </div>
  );
}

function LevelList({ title, levels, color }) {
  return (
    <div className="rounded-lg p-3" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
      <div className="text-[10px] tracking-wide mb-2" style={{ color }}>{title}</div>
      {levels?.length > 0 ? levels.map((level, i) => (
        <div key={i} className="flex justify-between py-1" style={{ borderBottom: i < levels.length - 1 ? '1px solid var(--color-border)' : 'none' }}>
          <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>{level.type}</span>
          <span className="text-xs font-mono" style={{ color }}>${level.price?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        </div>
      )) : (
        <div className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>No levels found</div>
      )}
    </div>
  );
}
