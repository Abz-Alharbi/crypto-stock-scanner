import React, { useState } from 'react';
import { AlertCircle, Filter, Zap, ChevronDown, ChevronRight, Play, RotateCcw, Save } from 'lucide-react';
import useMarketStore from '../../store/useMarketStore';
import useAuthStore from '../../store/useAuthStore';

const CATEGORY_LABELS = {
  oscillators: { label: 'Oscillators', icon: '📊', color: 'text-blue-400' },
  moving_averages: { label: 'Moving Averages', icon: '📈', color: 'text-emerald-400' },
  volatility: { label: 'Volatility', icon: '🌊', color: 'text-purple-400' },
  patterns: { label: 'Patterns', icon: '🔷', color: 'text-amber-400' },
  fibonacci: { label: 'Fibonacci', icon: '🔢', color: 'text-pink-400' },
};

export default function FilterPanel() {
  const {
    filterDefinitions, filterPresets, selectedFilters, timeframe, timeframes,
    filterError, scanTemplateError, isSavingScanTemplate,
    toggleFilter, setFiltersFromPreset, clearFilters, setTimeframe, runScan, saveScanTemplate, isScanning
  } = useMarketStore();
  const { isAuthenticated, setAuthModal } = useAuthStore();

  const [expandedCats, setExpandedCats] = useState(new Set(['oscillators', 'moving_averages']));
  const [templateName, setTemplateName] = useState('');
  const timeframeOptions = Object.entries(timeframes || {}).map(([key, config]) => ({
    key,
    label: config.label || key,
    shortLabel: config.short_label || key,
    available: config.available !== false,
  }));

  const toggleCategory = (cat) => {
    const next = new Set(expandedCats);
    next.has(cat) ? next.delete(cat) : next.add(cat);
    setExpandedCats(next);
  };

  const handleSaveTemplate = async (event) => {
    event.preventDefault();
    if (!isAuthenticated) {
      setAuthModal(true, 'login');
      return;
    }
    const name = templateName.trim();
    if (!name) return;
    await saveScanTemplate(name);
    setTemplateName('');
  };

  return (
    <div className="bg-scanner-card border border-scanner-border rounded-2xl overflow-hidden">
      {/* Panel Header */}
      <div className="p-4 border-b border-scanner-border bg-gradient-to-r from-scanner-card to-scanner-bg">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Filter size={18} className="text-scanner-accent" />
            <h2 className="font-display font-semibold text-base">Scan Filters</h2>
            {selectedFilters.length > 0 && (
              <span className="px-2 py-0.5 rounded-full bg-scanner-accent/10 text-scanner-accent text-xs font-mono">
                {selectedFilters.length}
              </span>
            )}
          </div>
          {selectedFilters.length > 0 && (
            <button onClick={clearFilters} className="flex items-center gap-1 text-xs text-scanner-text-dim hover:text-scanner-danger transition-colors">
              <RotateCcw size={12} /> Clear
            </button>
          )}
        </div>
      </div>

      {/* Timeframe Selector */}
      <div className="px-4 py-3 border-b border-scanner-border">
        <label className="block text-[10px] font-medium text-scanner-text-dim uppercase tracking-widest mb-2">Timeframe</label>
        <div className="flex gap-1">
          {timeframeOptions.map(tf => (
            <button
              key={tf.key}
              onClick={() => tf.available && setTimeframe(tf.key)}
              disabled={!tf.available}
              className={`flex-1 py-1.5 rounded-md text-xs font-semibold transition-all ${
                timeframe === tf.key
                  ? 'bg-scanner-accent text-scanner-bg shadow shadow-scanner-accent/30'
                  : !tf.available
                    ? 'bg-scanner-bg/40 text-scanner-text-dim/40 border border-dashed border-scanner-border cursor-not-allowed'
                  : 'bg-scanner-bg text-scanner-text-dim hover:text-scanner-text hover:bg-scanner-surface'
              }`}
              title={!tf.available ? 'Unavailable on the current data plan' : tf.label}
            >
              {tf.shortLabel}
            </button>
          ))}
        </div>
      </div>

      {filterError && (
        <div className="mx-4 mt-3 flex items-center gap-2 rounded-lg border border-scanner-danger/30 bg-scanner-danger/10 px-3 py-2 text-xs text-scanner-danger">
          <AlertCircle size={14} />
          <span>{filterError}</span>
        </div>
      )}

      {/* Presets */}
      <div className="px-4 py-3 border-b border-scanner-border">
        <label className="block text-[10px] font-medium text-scanner-text-dim uppercase tracking-widest mb-2">
          <Zap size={10} className="inline mr-1" />Quick Presets
        </label>
        <div className="grid grid-cols-2 gap-1.5">
          {Object.entries(filterPresets).map(([key, preset]) => (
            <button
              key={key}
              onClick={() => setFiltersFromPreset(key)}
              className="text-left px-3 py-2 rounded-lg bg-scanner-bg hover:bg-scanner-surface border border-scanner-border hover:border-scanner-accent/30 transition-all group"
            >
              <p className="text-xs font-medium text-scanner-text group-hover:text-scanner-accent transition-colors">{preset.name}</p>
              <p className="text-[10px] text-scanner-text-dim mt-0.5 line-clamp-1">{preset.description}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Save Template */}
      <form onSubmit={handleSaveTemplate} className="px-4 py-3 border-b border-scanner-border space-y-2">
        <label className="block text-[10px] font-medium text-scanner-text-dim uppercase tracking-widest">
          <Save size={10} className="inline mr-1" />Save Template
        </label>
        <div className="flex gap-2">
          <input
            value={templateName}
            onChange={(event) => setTemplateName(event.target.value)}
            maxLength={120}
            placeholder="Name this scan"
            className="min-w-0 flex-1 rounded-lg border border-scanner-border bg-scanner-bg px-3 py-2 text-xs text-scanner-text placeholder-scanner-text-dim focus:border-scanner-accent/50 focus:outline-none"
          />
          <button
            type="submit"
            disabled={isSavingScanTemplate || selectedFilters.length === 0 || !templateName.trim()}
            className="flex items-center justify-center rounded-lg bg-scanner-card px-3 py-2 text-xs font-semibold text-scanner-text-dim hover:text-scanner-accent disabled:cursor-not-allowed disabled:opacity-40"
          >
            {isSavingScanTemplate ? 'Saving' : 'Save'}
          </button>
        </div>
        {scanTemplateError && (
          <div className="flex items-center gap-2 rounded-lg border border-scanner-danger/30 bg-scanner-danger/10 px-3 py-2 text-xs text-scanner-danger">
            <AlertCircle size={14} />
            <span>{scanTemplateError}</span>
          </div>
        )}
      </form>

      {/* Filter Categories */}
      <div className="max-h-[400px] overflow-y-auto">
        {Object.entries(filterDefinitions).map(([catKey, filters]) => {
          const catInfo = CATEGORY_LABELS[catKey] || { label: catKey, icon: '🔹', color: 'text-gray-400' };
          const isExpanded = expandedCats.has(catKey);
          const selectedInCat = Object.keys(filters).filter(f => selectedFilters.includes(f)).length;

          return (
            <div key={catKey} className="border-b border-scanner-border last:border-b-0">
              <button
                onClick={() => toggleCategory(catKey)}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-scanner-bg/50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm">{catInfo.icon}</span>
                  <span className="text-sm font-medium">{catInfo.label}</span>
                  {selectedInCat > 0 && (
                    <span className="px-1.5 py-0.5 rounded-full bg-scanner-accent/20 text-scanner-accent text-[10px] font-mono">{selectedInCat}</span>
                  )}
                </div>
                {isExpanded ? <ChevronDown size={14} className="text-scanner-text-dim" /> : <ChevronRight size={14} className="text-scanner-text-dim" />}
              </button>

              {isExpanded && (
                <div className="px-4 pb-3 space-y-1 animate-fade-in">
                  {Object.entries(filters).map(([filterKey, filter]) => {
                    const isSelected = selectedFilters.includes(filterKey);
                    return (
                      <button
                        key={filterKey}
                        onClick={() => toggleFilter(filterKey)}
                        className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-all ${
                          isSelected
                            ? 'bg-scanner-accent/10 border border-scanner-accent/30'
                            : 'bg-scanner-bg/30 border border-transparent hover:border-scanner-border hover:bg-scanner-bg/60'
                        }`}
                      >
                        <div className={`w-4 h-4 rounded-md border-2 flex items-center justify-center flex-shrink-0 transition-all ${
                          isSelected ? 'bg-scanner-accent border-scanner-accent' : 'border-scanner-border'
                        }`}>
                          {isSelected && <svg width="10" height="8" viewBox="0 0 10 8" fill="none"><path d="M1 4L3.5 6.5L9 1" stroke="#0a0e17" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className={`text-xs font-medium ${isSelected ? 'text-scanner-accent' : 'text-scanner-text'}`}>{filter.name}</p>
                          <p className="text-[10px] text-scanner-text-dim truncate">{filter.description}</p>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Scan Button */}
      <div className="p-4 border-t border-scanner-border bg-scanner-bg/30">
        <button
          onClick={runScan}
          disabled={isScanning || selectedFilters.length === 0}
          className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-gradient-to-r from-scanner-accent to-emerald-500 text-scanner-bg font-bold text-sm hover:shadow-lg hover:shadow-scanner-accent/30 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {isScanning ? (
            <>
              <div className="w-4 h-4 border-2 border-scanner-bg border-t-transparent rounded-full animate-spin" />
              Scanning...
            </>
          ) : (
            <>
              <Play size={16} />
              Run Scan ({selectedFilters.length} filter{selectedFilters.length !== 1 ? 's' : ''})
            </>
          )}
        </button>
        <p className="text-center text-[10px] text-scanner-text-dim mt-2">
          Free tier: ~12s per stock (5 API calls/min)
        </p>
      </div>
    </div>
  );
}
