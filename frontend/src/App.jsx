import React, { useState, useEffect } from 'react';
import { TrendingUp, Filter, RefreshCw, AlertCircle, BarChart3, Activity, DollarSign, Clock } from 'lucide-react';
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';
const NasdaqScanner = () => {
  const [timeframe, setTimeframe] = useState('1d');
  const [filters, setFilters] = useState({
    ema: false,
    fibo: false,
    rsi: false,
    macd: false,
    volume: false
  });
  
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [scanTime, setScanTime] = useState(null);
  const [backendStatus, setBackendStatus] = useState('checking');
  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const [showPatternModal, setShowPatternModal] = useState(false);
  const [patternLoading, setPatternLoading] = useState(false);
  const [detailedPattern, setDetailedPattern] = useState(null);

  useEffect(() => {
    checkBackend();
  }, []);

  const checkBackend = async () => {
    try {
      const response = await fetch(`${API_URL}/health`);
      if (response.ok) {
        setBackendStatus('connected');
      } else {
        setBackendStatus('disconnected');
      }
    } catch (err) {
      setBackendStatus('disconnected');
    }
  };

  const AdSlot = ({ slot, className = '' }) => {
    const adSlotIds = {
      header: 'XXXXXXXXXX',
      sidebar: 'YYYYYYYYYY',
      footer: 'ZZZZZZZZZZ'
    };

    return (
      <div className={`ad-container ${className}`}>
        <ins
          className="adsbygoogle"
          style={{ display: 'block', minHeight: '90px' }}
          data-ad-client="ca-pub-XXXXXXXXXXXXXXXX"
          data-ad-slot={adSlotIds[slot]}
          data-ad-format="auto"
          data-full-width-responsive="true"
        />
        <div className="ad-fallback bg-gradient-to-r from-blue-500/10 to-indigo-500/10 border border-blue-500/30 rounded-lg p-4 text-center">
          <p className="text-blue-300 text-sm mb-2"><strong>Support Us</strong></p>
          <p className="text-blue-400 text-xs">This free tool is supported by ads</p>
        </div>
      </div>
    );
  };

  const handleFilterChange = (filterName) => {
    setFilters(prev => ({ ...prev, [filterName]: !prev[filterName] }));
  };

  const handleScan = async () => {
    setLoading(true);
    setError(null);
    setScanTime(null);
    setResults([]);
    setSelectedSymbol(null);
    setShowPatternModal(false);
    
    try {
      const selectedFilters = Object.keys(filters).filter(f => filters[f]);
      
      if (selectedFilters.length === 0) {
        setError('Please select at least one filter');
        setLoading(false);
        return;
      }

      const startTime = Date.now();
      
      const response = await fetch(`${API_URL}/filter`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({
          filters: selectedFilters,
          timeframe: timeframe
        }),
        mode: 'cors',
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const data = await response.json();
      
      const endTime = Date.now();
      setScanTime(((endTime - startTime) / 1000).toFixed(2));
      
      setResults(data);
      
      if (data.length === 0) {
        setError('No matches found. Try different filters.');
      }
      
    } catch (err) {
      console.error('Scan error:', err);
      setError(`Scan failed: ${err.message}`);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSymbolClick = async (symbol) => {
    setSelectedSymbol(symbol);
    setShowPatternModal(true);
    setPatternLoading(true);
    setDetailedPattern(null);

    try {
      const response = await fetch(`${API_URL}/pattern-analysis`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          symbol: symbol,
          timeframe: timeframe
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setDetailedPattern(data);
      }
    } catch (err) {
      console.error('Pattern analysis error:', err);
    } finally {
      setPatternLoading(false);
    }
  };

  const PatternModal = () => {
    if (!showPatternModal) return null;

    const getPatternDescription = (pattern) => {
      const descriptions = {
        'Head & Shoulders': {
          desc: 'A bearish reversal pattern with three peaks, the middle being the highest.',
          signal: 'Bearish',
          reliability: 'High',
          icon: '📉'
        },
        'Inverse Head & Shoulders': {
          desc: 'A bullish reversal pattern with three troughs, the middle being the lowest.',
          signal: 'Bullish',
          reliability: 'High',
          icon: '📈'
        },
        'Double Top': {
          desc: 'A bearish reversal pattern showing two peaks at similar price levels.',
          signal: 'Bearish',
          reliability: 'High',
          icon: '⚠️'
        },
        'Double Bottom': {
          desc: 'A bullish reversal pattern showing two troughs at similar price levels.',
          signal: 'Bullish',
          reliability: 'High',
          icon: '✅'
        },
        'Triple Top': {
          desc: 'A bearish reversal pattern with three peaks at approximately the same level.',
          signal: 'Bearish',
          reliability: 'Very High',
          icon: '🔴'
        },
        'Triple Bottom': {
          desc: 'A bullish reversal pattern with three troughs at approximately the same level.',
          signal: 'Bullish',
          reliability: 'Very High',
          icon: '🟢'
        },
        'Ascending Triangle': {
          desc: 'A bullish continuation pattern with a flat upper resistance and rising support.',
          signal: 'Bullish',
          reliability: 'Medium-High',
          icon: '📐'
        },
        'Descending Triangle': {
          desc: 'A bearish continuation pattern with a flat lower support and declining resistance.',
          signal: 'Bearish',
          reliability: 'Medium-High',
          icon: '📐'
        },
        'Symmetrical Triangle': {
          desc: 'A neutral pattern with converging trendlines, breakout direction determines trend.',
          signal: 'Neutral',
          reliability: 'Medium',
          icon: '🔺'
        },
        'Bull Flag': {
          desc: 'A bullish continuation pattern with a sharp rise followed by a slight downward drift.',
          signal: 'Bullish',
          reliability: 'High',
          icon: '🚩'
        },
        'Bear Flag': {
          desc: 'A bearish continuation pattern with a sharp decline followed by a slight upward drift.',
          signal: 'Bearish',
          reliability: 'High',
          icon: '🏴'
        },
        'Cup & Handle': {
          desc: 'A bullish continuation pattern resembling a tea cup with a handle.',
          signal: 'Bullish',
          reliability: 'High',
          icon: '☕'
        },
        'Bullish Trend': {
          desc: 'Price showing consistent upward movement with higher highs and higher lows.',
          signal: 'Bullish',
          reliability: 'Medium',
          icon: '🚀'
        },
        'Bearish Trend': {
          desc: 'Price showing consistent downward movement with lower lows and lower highs.',
          signal: 'Bearish',
          reliability: 'Medium',
          icon: '📉'
        },
        'Consolidation': {
          desc: 'Price moving sideways in a tight range, often precedes a breakout.',
          signal: 'Neutral',
          reliability: 'Low',
          icon: '➡️'
        }
      };
      return descriptions[pattern] || {
        desc: 'Pattern detected in price action.',
        signal: 'Neutral',
        reliability: 'Unknown',
        icon: '📊'
      };
    };

    const patternInfo = detailedPattern && detailedPattern.patterns.length > 0 
      ? getPatternDescription(detailedPattern.patterns[0])
      : null;

    return (
      <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
           onClick={() => setShowPatternModal(false)}>
        <div className="bg-gradient-to-br from-slate-800 to-blue-900 rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto border border-blue-500/30 shadow-2xl"
             onClick={(e) => e.stopPropagation()}>
          
          {/* Header */}
          <div className="bg-black/30 p-6 border-b border-blue-500/30">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold text-white">Pattern Analysis</h2>
                <p className="text-blue-300 text-sm mt-1">{selectedSymbol} • {timeframe === '1d' ? 'Daily' : 'Weekly'}</p>
              </div>
              <button
                onClick={() => setShowPatternModal(false)}
                className="text-white hover:text-red-400 transition-colors"
              >
                <AlertCircle className="w-6 h-6" />
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="p-6">
            {patternLoading ? (
              <div className="text-center py-12">
                <RefreshCw className="w-12 h-12 text-blue-400 mx-auto mb-4 animate-spin" />
                <p className="text-blue-300">Analyzing chart patterns...</p>
              </div>
            ) : detailedPattern && detailedPattern.patterns.length > 0 ? (
              <div className="space-y-6">
                {/* Main Pattern */}
                <div className="bg-white/10 rounded-xl p-6 border border-white/20">
                  <div className="flex items-start gap-4">
                    <div className="text-5xl">{patternInfo.icon}</div>
                    <div className="flex-1">
                      <h3 className="text-2xl font-bold text-white mb-2">
                        {detailedPattern.patterns[0]}
                      </h3>
                      <p className="text-blue-200 mb-4">{patternInfo.desc}</p>
                      
                      <div className="grid grid-cols-3 gap-4">
                        <div className="bg-black/30 rounded-lg p-3">
                          <div className="text-xs text-blue-300 mb-1">Signal</div>
                          <div className={`font-bold ${
                            patternInfo.signal === 'Bullish' ? 'text-green-400' : 
                            patternInfo.signal === 'Bearish' ? 'text-red-400' : 'text-yellow-400'
                          }`}>
                            {patternInfo.signal}
                          </div>
                        </div>
                        <div className="bg-black/30 rounded-lg p-3">
                          <div className="text-xs text-blue-300 mb-1">Reliability</div>
                          <div className="font-bold text-white">{patternInfo.reliability}</div>
                        </div>
                        <div className="bg-black/30 rounded-lg p-3">
                          <div className="text-xs text-blue-300 mb-1">Confidence</div>
                          <div className="font-bold text-white">{detailedPattern.confidence}%</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Additional Patterns */}
                {detailedPattern.patterns.length > 1 && (
                  <div>
                    <h4 className="text-lg font-semibold text-white mb-3">Additional Patterns Detected</h4>
                    <div className="space-y-2">
                      {detailedPattern.patterns.slice(1).map((pattern, idx) => {
                        const info = getPatternDescription(pattern);
                        return (
                          <div key={idx} className="bg-white/5 rounded-lg p-4 border border-white/10">
                            <div className="flex items-center gap-3">
                              <span className="text-2xl">{info.icon}</span>
                              <div className="flex-1">
                                <div className="font-semibold text-white">{pattern}</div>
                                <div className="text-sm text-blue-300">{info.desc}</div>
                              </div>
                              <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                                info.signal === 'Bullish' ? 'bg-green-500/20 text-green-300' :
                                info.signal === 'Bearish' ? 'bg-red-500/20 text-red-300' :
                                'bg-yellow-500/20 text-yellow-300'
                              }`}>
                                {info.signal}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Support & Resistance Levels */}
                {detailedPattern.support_resistance && (
                  <div>
                    <h4 className="text-lg font-semibold text-white mb-3">Key Levels</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
                        <div className="text-sm text-green-300 mb-1">Support Level</div>
                        <div className="text-2xl font-bold text-green-400">
                          ${detailedPattern.support_resistance.support}
                        </div>
                      </div>
                      <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
                        <div className="text-sm text-red-300 mb-1">Resistance Level</div>
                        <div className="text-2xl font-bold text-red-400">
                          ${detailedPattern.support_resistance.resistance}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Educational Note */}
                <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <div className="font-semibold text-yellow-200 mb-1">Educational Note</div>
                      <div className="text-sm text-yellow-100">
                        Pattern analysis is for educational purposes only. Always conduct your own research 
                        and never invest more than you can afford to lose.
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-12">
                <BarChart3 className="w-16 h-16 text-blue-400 mx-auto mb-4 opacity-50" />
                <p className="text-blue-300 mb-2">No clear patterns detected</p>
                <p className="text-blue-400 text-sm">
                  The price action doesn't show any recognizable technical patterns at this time.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  const filterOptions = [
    { id: 'ema', label: 'EMA Crossover', icon: TrendingUp, desc: 'EMA 50 > EMA 200' },
    { id: 'fibo', label: 'Fibonacci 50%', icon: BarChart3, desc: 'Price ≥ Fib Level' },
    { id: 'rsi', label: 'RSI > 50', icon: Activity, desc: 'Momentum positive' },
    { id: 'macd', label: 'MACD > 0', icon: TrendingUp, desc: 'Bullish momentum' },
    { id: 'volume', label: 'Volume Spike', icon: BarChart3, desc: '2x avg volume' }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900">
      {/* Pattern Modal */}
      <PatternModal />
      
      {/* Header */}
      <header className="bg-black/30 backdrop-blur-sm border-b border-blue-500/30">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-3">
              <div className="bg-blue-500 p-2 rounded-lg">
                <DollarSign className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white">NASDAQ Scanner Pro</h1>
                <p className="text-blue-300 text-sm">1000+ Most Active Stocks</p>
              </div>
            </div>
            <div className={`px-4 py-2 rounded-lg ${backendStatus === 'connected' ? 'bg-green-500/20 border border-green-500/50' : 'bg-red-500/20 border border-red-500/50'}`}>
              <div className="text-xs text-white">
                {backendStatus === 'connected' ? '✅ Backend Connected' : '❌ Backend Offline'}
              </div>
            </div>
          </div>
        </div>
        <div className="container mx-auto px-4 py-2">
          <AdSlot slot="header" className="max-w-4xl mx-auto" />
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        {/* Disclaimer */}
        <div className="mb-6 bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-yellow-100">
              <strong>Disclaimer:</strong> This site is for educational purposes only and is not financial advice. 
              Always conduct your own research before making investment decisions.
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-3 space-y-6">
            
            {/* Time Interval Selection - Radio Buttons */}
            <div className="bg-white/10 backdrop-blur-md rounded-xl p-6 border border-white/20">
              <div className="flex items-center gap-2 mb-4">
                <Clock className="w-5 h-5 text-blue-400" />
                <h2 className="text-xl font-bold text-white">Time Interval</h2>
              </div>
              
              <div className="flex flex-wrap gap-6">
                {/* Daily Radio */}
                <label className="flex items-center gap-3 cursor-pointer group">
                  <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all ${
                    timeframe === '1d' 
                      ? 'border-blue-400' 
                      : 'border-white/30 group-hover:border-blue-400/50'
                  }`}>
                    {timeframe === '1d' && <div className="w-2.5 h-2.5 rounded-full bg-blue-400" />}
                  </div>
                  <input
                    type="radio"
                    name="timeframe"
                    value="1d"
                    checked={timeframe === '1d'}
                    onChange={(e) => setTimeframe(e.target.value)}
                    className="hidden"
                  />
                  <div>
                    <span className={`font-semibold ${timeframe === '1d' ? 'text-blue-300' : 'text-white'}`}>
                      Daily
                    </span>
                    <span className="text-blue-400 text-sm ml-2">(1 Day Candles)</span>
                  </div>
                </label>

                {/* Weekly Radio */}
                <label className="flex items-center gap-3 cursor-pointer group">
                  <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all ${
                    timeframe === '1wk' 
                      ? 'border-blue-400' 
                      : 'border-white/30 group-hover:border-blue-400/50'
                  }`}>
                    {timeframe === '1wk' && <div className="w-2.5 h-2.5 rounded-full bg-blue-400" />}
                  </div>
                  <input
                    type="radio"
                    name="timeframe"
                    value="1wk"
                    checked={timeframe === '1wk'}
                    onChange={(e) => setTimeframe(e.target.value)}
                    className="hidden"
                  />
                  <div>
                    <span className={`font-semibold ${timeframe === '1wk' ? 'text-blue-300' : 'text-white'}`}>
                      Weekly
                    </span>
                    <span className="text-blue-400 text-sm ml-2">(1 Week Candles)</span>
                  </div>
                </label>
              </div>
            </div>

            {/* Filter Selection */}
            <div className="bg-white/10 backdrop-blur-md rounded-xl p-6 border border-white/20">
              <div className="flex items-center gap-2 mb-4">
                <Filter className="w-5 h-5 text-blue-400" />
                <h2 className="text-xl font-bold text-white">Select Technical Filters</h2>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                {filterOptions.map(option => {
                  const Icon = option.icon;
                  return (
                    <button
                      key={option.id}
                      onClick={() => handleFilterChange(option.id)}
                      className={`p-4 rounded-lg border-2 transition-all ${
                        filters[option.id]
                          ? 'bg-blue-500 border-blue-400 shadow-lg shadow-blue-500/50'
                          : 'bg-white/5 border-white/20 hover:border-blue-400/50'
                      }`}
                    >
                      <Icon className={`w-6 h-6 mb-2 ${filters[option.id] ? 'text-white' : 'text-blue-300'}`} />
                      <div className={`font-semibold mb-1 ${filters[option.id] ? 'text-white' : 'text-blue-100'}`}>
                        {option.label}
                      </div>
                      <div className={`text-xs ${filters[option.id] ? 'text-blue-100' : 'text-blue-300'}`}>
                        {option.desc}
                      </div>
                    </button>
                  );
                })}
              </div>

              <button
                onClick={handleScan}
                disabled={loading}
                className="w-full bg-gradient-to-r from-blue-500 to-indigo-500 hover:from-blue-600 hover:to-indigo-600
                           disabled:from-gray-500 disabled:to-gray-600 text-white font-semibold py-4 rounded-lg 
                           transition-all flex items-center justify-center gap-2 shadow-lg"
              >
                <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
                {loading ? 'Scanning NASDAQ...' : `Scan NASDAQ (${timeframe === '1d' ? 'Daily' : 'Weekly'})`}
              </button>
              
              {loading && (
                <div className="mt-4">
                  <div className="bg-white/10 rounded-full h-3 overflow-hidden">
                    <div className="bg-gradient-to-r from-blue-500 to-indigo-500 h-full animate-pulse w-full" />
                  </div>
                  <p className="text-center text-blue-300 text-sm mt-2">
                    Scanning 1000+ stocks with {timeframe === '1d' ? 'daily' : 'weekly'} data...
                  </p>
                </div>
              )}
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
                <div className="flex items-center gap-2 text-red-300">
                  <AlertCircle className="w-5 h-5" />
                  <div className="font-semibold">{error}</div>
                </div>
              </div>
            )}

            {scanTime && (
              <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
                <div className="text-green-300 text-sm">
                  Scan completed in <strong>{scanTime}s</strong> • Found <strong>{results.length}</strong> matches • Timeframe: <strong>{timeframe === '1d' ? 'Daily' : 'Weekly'}</strong>
                </div>
              </div>
            )}

            {results.length > 0 && (
              <div className="bg-white/10 backdrop-blur-md rounded-xl p-6 border border-white/20 overflow-x-auto">
                <h2 className="text-xl font-bold text-white mb-4">
                  Scan Results - NASDAQ Stocks
                </h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="border-b border-white/20">
                        <th className="pb-3 text-blue-300 font-semibold">Symbol</th>
                        <th className="pb-3 text-blue-300 font-semibold">Price</th>
                        <th className="pb-3 text-blue-300 font-semibold">Filters Passed</th>
                        {filters.ema && (
                          <>
                            <th className="pb-3 text-blue-300 font-semibold">EMA 50</th>
                            <th className="pb-3 text-blue-300 font-semibold">EMA 200</th>
                          </>
                        )}
                        {filters.rsi && <th className="pb-3 text-blue-300 font-semibold">RSI</th>}
                        {filters.macd && <th className="pb-3 text-blue-300 font-semibold">MACD</th>}
                        {filters.fibo && <th className="pb-3 text-blue-300 font-semibold">Fibo 50%</th>}
                        {filters.volume && <th className="pb-3 text-blue-300 font-semibold">Volume Status</th>}
                        <th className="pb-3 text-blue-300 font-semibold">Pattern</th>
                      </tr>
                    </thead>
                    <tbody>
                      {results.map((result, idx) => (
                        <tr key={idx} className="border-b border-white/10 hover:bg-white/5">
                          <td className="py-3">
                            <button
                              onClick={() => handleSymbolClick(result.symbol)}
                              className="text-white font-bold hover:text-blue-400 transition-colors underline decoration-dotted"
                            >
                              {result.symbol}
                            </button>
                          </td>
                          <td className="py-3 text-white font-semibold">
                            ${result.values?.last_price || '-'}
                          </td>
                          <td className="py-3">
                            <div className="flex flex-wrap gap-1">
                              {result.filters && result.filters.map(f => (
                                <span key={f} className="px-2 py-1 bg-green-500/30 text-green-200 text-xs rounded font-semibold">
                                  ✓ {f.toUpperCase()}
                                </span>
                              ))}
                            </div>
                          </td>
                          {filters.ema && (
                            <>
                              <td className="py-3 text-green-300 font-semibold">{result.values?.ema_50 || '-'}</td>
                              <td className="py-3 text-green-300">{result.values?.ema_200 || '-'}</td>
                            </>
                          )}
                          {filters.rsi && (
                            <td className="py-3 text-yellow-300 font-semibold">{result.values?.rsi || '-'}</td>
                          )}
                          {filters.macd && (
                            <td className="py-3 text-purple-300 font-semibold">{result.values?.macd || '-'}</td>
                          )}
                          {filters.fibo && (
                            <td className="py-3 text-blue-300 font-semibold">{result.values?.fibo || '-'}</td>
                          )}
                          {filters.volume && (
                            <td className="py-3">
                              {result.filters.includes('volume') ? (
                                <span className="px-2 py-1 bg-green-500/30 text-green-200 text-xs rounded font-semibold">
                                  🔥 SPIKE
                                </span>
                              ) : (
                                <span className="text-gray-400 text-xs">Normal</span>
                              )}
                            </td>
                          )}
                          <td className="py-3 text-white">{result.pattern || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {!loading && results.length === 0 && !error && (
              <div className="bg-white/5 backdrop-blur-md rounded-xl p-12 border border-white/10 text-center">
                <BarChart3 className="w-16 h-16 text-blue-400 mx-auto mb-4" />
                <h3 className="text-xl font-bold text-white mb-2">Ready to Scan</h3>
                <p className="text-blue-300">
                  Select your time interval and filters, then click "Scan NASDAQ" to analyze stock data
                </p>
              </div>
            )}
          </div>

          <div className="lg:col-span-1 space-y-6">
            <div className="sticky top-4">
              <AdSlot slot="sidebar" />
            </div>
          </div>
        </div>

        <div className="mt-12">
          <AdSlot slot="footer" className="max-w-4xl mx-auto" />
        </div>
      </div>

      <footer className="bg-black/30 backdrop-blur-sm border-t border-blue-500/30 mt-12 py-8">
        <div className="container mx-auto px-4 text-center text-blue-300 text-sm">
          <p>NASDAQ Scanner Pro © 2026 • Educational Tool • Not Financial Advice</p>
          <p className="mt-2 text-xs text-blue-400">
            Real market data • 1000+ Stocks • Daily & Weekly Analysis
          </p>
        </div>
      </footer>
    </div>
  );
};

export default NasdaqScanner;