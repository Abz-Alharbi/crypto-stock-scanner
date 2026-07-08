import React from 'react';

export default function IndicatorLegend({ items, onToggle }) {
  if (!items || items.length === 0) return null;

  return (
    <div className="absolute left-3 top-3 z-20 max-w-[230px] rounded-lg border border-scanner-border bg-scanner-surface/90 p-2 text-xs shadow-scanner-sm backdrop-blur">
      <div className="space-y-1">
        {items.map(item => (
          <label
            key={item.key}
            className="flex min-w-0 items-center gap-2 rounded-md px-1.5 py-1 hover:bg-scanner-card/70"
          >
            <input
              type="checkbox"
              checked={item.visible}
              onChange={() => onToggle(item.key)}
              className="h-3.5 w-3.5 shrink-0 accent-scanner-accent"
              aria-label={`Toggle ${item.name}`}
            />
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: item.color }}
              aria-hidden="true"
            />
            <span className={`min-w-0 flex-1 truncate font-medium ${item.visible ? 'text-scanner-text' : 'text-scanner-text-dim line-through'}`}>
              {item.name}
            </span>
            <span className="shrink-0 font-mono text-[10px] text-scanner-text-dim">
              {item.value}
            </span>
          </label>
        ))}
      </div>
    </div>
  );
}
