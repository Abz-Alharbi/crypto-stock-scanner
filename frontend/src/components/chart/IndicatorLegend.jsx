import React from 'react';

export default function IndicatorLegend({ items, onToggle }) {
  if (!items || items.length === 0) return null;

  return (
    <div className="rounded-lg border border-scanner-border bg-scanner-surface px-2 py-1.5 text-xs shadow-scanner-sm">
      <div className="flex flex-wrap items-center gap-1.5">
        {items.map(item => (
          <button
            type="button"
            key={item.key}
            onClick={() => onToggle(item.key)}
            className={`inline-flex h-7 max-w-full items-center gap-1.5 rounded-full border px-2 transition-colors hover:border-scanner-accent/50 hover:bg-scanner-card ${
              item.visible
                ? 'border-scanner-border bg-scanner-bg text-scanner-text'
                : 'border-scanner-border/60 bg-scanner-bg text-scanner-text-dim opacity-70'
            }`}
            aria-pressed={item.visible}
            aria-label={`Toggle ${item.name}`}
          >
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: item.color }}
              aria-hidden="true"
            />
            <span className={`shrink-0 font-semibold ${item.visible ? '' : 'line-through'}`}>
              {item.shortName || item.name}
            </span>
            <span className={`max-w-[92px] truncate font-mono text-[10px] ${item.visible ? 'text-scanner-text-dim' : 'text-scanner-text-dim line-through'}`}>
              {item.value}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
