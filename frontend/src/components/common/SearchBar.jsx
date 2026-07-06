import React, { useState, useRef, useEffect } from 'react';
import { Search, X } from 'lucide-react';
import useMarketStore from '../../store/useMarketStore';

export default function SearchBar() {
  const { searchTickers, searchResults, isSearching, openDetail, activeMarket } = useMarketStore();
  const [query, setQuery] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const inputRef = useRef(null);
  const dropdownRef = useRef(null);
  const debounceRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target) && inputRef.current && !inputRef.current.contains(e.target)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      searchTickers('');
    };
  }, [searchTickers]);

  const handleChange = (e) => {
    const val = e.target.value;
    setQuery(val);
    setShowDropdown(true);

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      searchTickers(val);
    }, 300);
  };

  const handleSelect = (item) => {
    openDetail(item.provider_symbol || item.ticker);
    setQuery('');
    setShowDropdown(false);
  };

  return (
    <div className="relative w-full max-w-md">
      <div className="relative">
        <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-scanner-text-dim" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={handleChange}
          onFocus={() => query && setShowDropdown(true)}
          placeholder={`Search ${activeMarket === 'stocks' ? 'stocks' : 'crypto'}... (e.g., ${activeMarket === 'stocks' ? 'AAPL' : 'BTC'})`}
          className="w-full pl-10 pr-10 py-2.5 bg-scanner-bg border border-scanner-border rounded-xl text-sm placeholder-scanner-text-dim focus:outline-none focus:border-scanner-accent/50 transition-colors"
        />
        {query && (
          <button onClick={() => { setQuery(''); setShowDropdown(false); searchTickers(''); }} className="absolute right-3 top-1/2 -translate-y-1/2 text-scanner-text-dim hover:text-scanner-text">
            <X size={14} />
          </button>
        )}
        {isSearching && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <div className="w-3.5 h-3.5 border-2 border-scanner-border border-t-scanner-accent rounded-full animate-spin" />
          </div>
        )}
      </div>

      {/* Dropdown */}
      {showDropdown && searchResults.length > 0 && (
        <div ref={dropdownRef} className="absolute top-full left-0 right-0 mt-1 bg-scanner-card border border-scanner-border rounded-xl shadow-2xl z-50 max-h-64 overflow-y-auto animate-slide-down">
          {searchResults.map((item) => (
            <button
              key={item.provider_symbol || item.ticker}
              onClick={() => handleSelect(item)}
              className="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-scanner-bg/50 transition-colors first:rounded-t-xl last:rounded-b-xl"
            >
              <span className="font-mono font-bold text-scanner-accent text-sm w-20">{item.display_symbol || item.ticker}</span>
              <span className="text-xs text-scanner-text-dim truncate flex-1">{item.name}</span>
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-scanner-bg text-scanner-text-dim uppercase">{item.market}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
