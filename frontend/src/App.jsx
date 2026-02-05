import React, { useState, useEffect } from 'react';
import { TrendingUp, Filter, RefreshCw, AlertCircle, BarChart3, Activity, Clock, Search, X, CheckCircle, XCircle, TrendingDown, Zap } from 'lucide-react';

const NasdaqScanner = () => {
  const [timeframe, setTimeframe] = useState('1d');
  
  // Shared filters for both search modes
  const [filters, setFilters] = useState({
    ema: false,
    fibo: false,
    rsi: false,
    macd: false,
    volume: false
  });
  
  // Additional filters for single stock analysis
  const [advancedFilters, setAdvancedFilters] = useState({
    macd_crossover: false,
    rsi_oversold: false,
    rsi_overbought: false,
    bb_oversold: false,
    bb_overbought: false,
    trend_up: false,
    trend_down: false
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

  // Search feature states
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [showSearchResults, setShowSearchResults] = useState(false);
  const [analyzeResult, setAnalyzeResult] = useState(null);
  const [analyzeLoading, setAnalyzeLoading] = useState(false);
  const [showAnalyzeModal, setShowAnalyzeModal] = useState(false);

  useEffect(() => {
    checkBackend();
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchQuery.length >= 1) {
        searchStocks(searchQuery);
      } else {
        setSearchResults([]);
        setShowSearchResults(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const checkBackend = async () => {
    try {
      const response = await fetch('http://localhost:5000/health');
      if (response.ok) {
        setBackendStatus('connected');
      } else {
        setBackendStatus('disconnected');
      }
    } catch (err) {
      setBackendStatus('disconnected');
    }
  };

  const searchStocks = async (query) => {
    setSearchLoading(true);
    try {
      const response = await fetch(`http://localhost:5000/search-stocks?q=${encodeURIComponent(query)}`);
      if (response.ok) {
        const data = await response.json();
        setSearchResults(data);
        setShowSearchResults(true);
      }
    } catch (err) {
      console.error('Search error:', err);
    } finally {
      setSearchLoading(false);
    }
  };

  const handleAnalyzeStock = async (symbol) => {
    setSearchQuery(symbol);
    setShowSearchResults(false);
    setAnalyzeLoading(true);
    setShowAnalyzeModal(true);
    setAnalyzeResult(null);

    // Combine basic and advanced filters
    const selectedBasicFilters = Object.keys(filters).filter(f => filters[f]);
    const selectedAdvancedFilters = Object.keys(advancedFilters).filter(f => advancedFilters[f]);
    const allSelectedFilters = [...selectedBasicFilters, ...selectedAdvancedFilters];

    try {
      const response = await fetch('http://localhost:5000/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: symbol,
          filters: allSelectedFilters,
          timeframe: timeframe
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setAnalyzeResult(data);
      } else {
        setAnalyzeResult({ success: false, error: 'Failed to analyze stock' });
      }
    } catch (err) {
      console.error('Analyze error:', err);
      setAnalyzeResult({ success: false, error: 'Failed to connect to server' });
    } finally {
      setAnalyzeLoading(false);
    }
  };

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      handleAnalyzeStock(searchQuery.trim().toUpperCase());
    }
  };

  const handleFilterChange = (filterName) => {
    setFilters(prev => ({ ...prev, [filterName]: !prev[filterName] }));
  };

  const handleAdvancedFilterChange = (filterName) => {
    setAdvancedFilters(prev => ({ ...prev, [filterName]: !prev[filterName] }));
  };

  const handleScan = async () => {
    setLoading(true);
    setError(null);
    setScanTime(null);
    setResults([]);
    
    try {
      const selectedFilters = Object.keys(filters).filter(f => filters[f]);
      
      if (selectedFilters.length === 0) {
        setError('Please select at least one filter');
        setLoading(false);
        return;
      }

      const startTime = Date.now();
      
      const response = await fetch('http://localhost:5000/filter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filters: selectedFilters,
          timeframe: timeframe
        }),
      });

      if (!response.ok) throw new Error(`Server returned ${response.status}`);

      const data = await response.json();
      const endTime = Date.now();
      setScanTime(((endTime - startTime) / 1000).toFixed(2));
      setResults(data);
      
      if (data.length === 0) setError('No matches found. Try different filters.');
      
    } catch (err) {
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
      const response = await fetch('http://localhost:5000/pattern-analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: symbol, timeframe: timeframe }),
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

  // Analysis Modal
  const AnalyzeModal = () => {
    if (!showAnalyzeModal) return null;

    return (
      <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
        <div className="bg-gradient-to-br from-gray-900 to-gray-800 rounded-2xl p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto border border-blue-500/30">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-white flex items-center gap-2">
              <Search className="w-6 h-6 text-blue-400" />
              Stock Analysis
            </h2>
            <button onClick={() => setShowAnalyzeModal(false)} className="text-gray-400 hover:text-white">
              <X className="w-6 h-6" />
            </button>
          </div>

          {analyzeLoading ? (
            <div className="text-center py-12">
              <RefreshCw className="w-12 h-12 text-blue-400 animate-spin mx-auto mb-4" />
              <p className="text-blue-300">Analyzing {searchQuery}...</p>
            </div>
          ) : analyzeResult ? (
            !analyzeResult.success ? (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-6 text-center">
                <XCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
                <p className="text-red-300 font-semibold">{analyzeResult.error || 'Could not fetch data for this symbol'}</p>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Stock Header */}
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                    <div>
                      <h3 className="text-3xl font-bold text-white">{analyzeResult.symbol}</h3>
                      <p className="text-blue-300 text-lg">{analyzeResult.name}</p>
                      {analyzeResult.stock_info?.sector && (
                        <p className="text-blue-400 text-sm">{analyzeResult.stock_info.sector} • {analyzeResult.stock_info.industry}</p>
                      )}
                    </div>
                    <div className="text-right">
                      <p className="text-4xl font-bold text-green-400">${analyzeResult.indicators?.last_price}</p>
                      <p className="text-blue-300 text-sm">{analyzeResult.timeframe} Analysis</p>
                    </div>
                  </div>
                </div>

                {/* Status */}
                {analyzeResult.status && analyzeResult.status !== 'info' && (
                  <div className={`rounded-lg p-4 ${
                    analyzeResult.status === 'all_passed' ? 'bg-green-500/20 border border-green-500/50' :
                    analyzeResult.status === 'partial' ? 'bg-yellow-500/20 border border-yellow-500/50' :
                    'bg-red-500/20 border border-red-500/50'
                  }`}>
                    <p className={`text-lg font-semibold ${
                      analyzeResult.status === 'all_passed' ? 'text-green-300' :
                      analyzeResult.status === 'partial' ? 'text-yellow-300' : 'text-red-300'
                    }`}>
                      {analyzeResult.message}
                    </p>
                  </div>
                )}

                {/* Pattern Analysis */}
                {analyzeResult.advanced_patterns && (
                  <div className="bg-purple-500/10 border border-purple-500/30 rounded-lg p-4">
                    <h4 className="text-lg font-semibold text-purple-400 mb-3 flex items-center gap-2">
                      <BarChart3 className="w-5 h-5" />
                      Pattern Analysis
                    </h4>
                    
                    {analyzeResult.advanced_patterns.pattern_details?.length > 0 ? (
                      <div className="space-y-3">
                        {analyzeResult.advanced_patterns.pattern_details.map((pattern, idx) => (
                          <div key={idx} className="bg-white/5 rounded-lg p-3">
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-white font-semibold text-lg">{pattern.name}</span>
                              <span className={`px-2 py-1 rounded text-sm ${
                                pattern.signal === 'Buy' || pattern.signal === 'Hold/Buy' ? 'bg-green-500/30 text-green-300' :
                                pattern.signal === 'Sell' || pattern.signal === 'Hold/Sell' ? 'bg-red-500/30 text-red-300' :
                                'bg-yellow-500/30 text-yellow-300'
                              }`}>
                                {pattern.signal}
                              </span>
                            </div>
                            <p className="text-gray-300 text-sm">{pattern.description}</p>
                            <div className="flex gap-2 mt-2">
                              <span className="text-xs px-2 py-1 bg-purple-500/20 text-purple-300 rounded">{pattern.type}</span>
                              <span className="text-xs px-2 py-1 bg-blue-500/20 text-blue-300 rounded">{pattern.reliability} Reliability</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-gray-400">No specific patterns detected</p>
                    )}
                    
                    {analyzeResult.advanced_patterns.support_resistance && (
                      <div className="mt-4 flex gap-4">
                        <div className="flex-1 bg-green-500/10 rounded-lg p-3 text-center">
                          <p className="text-green-300 text-xs">Support</p>
                          <p className="text-green-400 font-bold text-xl">${analyzeResult.advanced_patterns.support_resistance.support}</p>
                        </div>
                        <div className="flex-1 bg-red-500/10 rounded-lg p-3 text-center">
                          <p className="text-red-300 text-xs">Resistance</p>
                          <p className="text-red-400 font-bold text-xl">${analyzeResult.advanced_patterns.support_resistance.resistance}</p>
                        </div>
                      </div>
                    )}
                    
                    {analyzeResult.advanced_patterns.confidence > 0 && (
                      <div className="mt-4">
                        <div className="flex justify-between text-sm mb-1">
                          <span className="text-purple-300">Pattern Confidence</span>
                          <span className="text-white">{analyzeResult.advanced_patterns.confidence}%</span>
                        </div>
                        <div className="w-full bg-gray-700 rounded-full h-2">
                          <div className="bg-gradient-to-r from-purple-500 to-pink-500 h-2 rounded-full" style={{ width: `${analyzeResult.advanced_patterns.confidence}%` }} />
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Filters Passed */}
                {analyzeResult.filters_passed?.length > 0 && (
                  <div>
                    <h4 className="text-lg font-semibold text-green-400 mb-3 flex items-center gap-2">
                      <CheckCircle className="w-5 h-5" />
                      Filters Passed ({analyzeResult.filters_passed.length})
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {analyzeResult.filters_passed.map((filter, idx) => (
                        <div key={idx} className="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
                          <div className="flex items-center justify-between">
                            <span className="text-green-300 font-semibold">{filter.name}</span>
                            <span className="text-green-400 text-sm">✓</span>
                          </div>
                          <p className="text-green-200 text-sm mt-1">{filter.value}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Filters Failed */}
                {analyzeResult.filters_failed?.length > 0 && (
                  <div>
                    <h4 className="text-lg font-semibold text-red-400 mb-3 flex items-center gap-2">
                      <XCircle className="w-5 h-5" />
                      Filters Failed ({analyzeResult.filters_failed.length})
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {analyzeResult.filters_failed.map((filter, idx) => (
                        <div key={idx} className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                          <div className="flex items-center justify-between">
                            <span className="text-red-300 font-semibold">{filter.name}</span>
                            <span className="text-red-400 text-sm">✗</span>
                          </div>
                          <p className="text-red-200 text-sm mt-1">{filter.value}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Technical Indicators */}
                {analyzeResult.indicators && (
                  <div>
                    <h4 className="text-lg font-semibold text-blue-400 mb-3">Technical Indicators</h4>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      <div className="bg-white/5 rounded-lg p-3 text-center">
                        <p className="text-blue-300 text-xs">EMA 20</p>
                        <p className="text-white font-bold">{analyzeResult.indicators.ema_20 || '-'}</p>
                      </div>
                      <div className="bg-white/5 rounded-lg p-3 text-center">
                        <p className="text-blue-300 text-xs">EMA 50</p>
                        <p className="text-white font-bold">{analyzeResult.indicators.ema_50 || '-'}</p>
                      </div>
                      <div className="bg-white/5 rounded-lg p-3 text-center">
                        <p className="text-blue-300 text-xs">EMA 200</p>
                        <p className="text-white font-bold">{analyzeResult.indicators.ema_200 || '-'}</p>
                      </div>
                      <div className="bg-white/5 rounded-lg p-3 text-center">
                        <p className="text-blue-300 text-xs">RSI</p>
                        <p className={`font-bold ${
                          analyzeResult.indicators.rsi > 70 ? 'text-red-400' :
                          analyzeResult.indicators.rsi < 30 ? 'text-green-400' : 'text-white'
                        }`}>{analyzeResult.indicators.rsi || '-'}</p>
                      </div>
                      <div className="bg-white/5 rounded-lg p-3 text-center">
                        <p className="text-blue-300 text-xs">MACD</p>
                        <p className={`font-bold ${analyzeResult.indicators.macd > 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {analyzeResult.indicators.macd || '-'}
                        </p>
                      </div>
                      <div className="bg-white/5 rounded-lg p-3 text-center">
                        <p className="text-blue-300 text-xs">MACD Signal</p>
                        <p className="text-white font-bold">{analyzeResult.indicators.macd_signal || '-'}</p>
                      </div>
                      <div className="bg-white/5 rounded-lg p-3 text-center">
                        <p className="text-blue-300 text-xs">Stochastic %K</p>
                        <p className="text-white font-bold">{analyzeResult.indicators.stochastic_k || '-'}</p>
                      </div>
                      <div className="bg-white/5 rounded-lg p-3 text-center">
                        <p className="text-blue-300 text-xs">ATR</p>
                        <p className="text-white font-bold">{analyzeResult.indicators.atr || '-'}</p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Bollinger Bands */}
                {analyzeResult.bollinger_bands && (
                  <div className="bg-white/5 rounded-lg p-4">
                    <h4 className="text-blue-400 font-semibold mb-3">Bollinger Bands</h4>
                    <div className="grid grid-cols-3 gap-3">
                      <div className="text-center">
                        <p className="text-red-300 text-xs">Upper Band</p>
                        <p className="text-red-400 font-bold">${analyzeResult.bollinger_bands.upper}</p>
                      </div>
                      <div className="text-center">
                        <p className="text-blue-300 text-xs">Middle (SMA 20)</p>
                        <p className="text-white font-bold">${analyzeResult.bollinger_bands.middle}</p>
                      </div>
                      <div className="text-center">
                        <p className="text-green-300 text-xs">Lower Band</p>
                        <p className="text-green-400 font-bold">${analyzeResult.bollinger_bands.lower}</p>
                      </div>
                    </div>
                    <p className="text-center mt-2 text-sm">
                      <span className={`px-2 py-1 rounded ${
                        analyzeResult.bollinger_bands.position === 'Above Upper' ? 'bg-red-500/30 text-red-300' :
                        analyzeResult.bollinger_bands.position === 'Below Lower' ? 'bg-green-500/30 text-green-300' :
                        'bg-blue-500/30 text-blue-300'
                      }`}>
                        Price is {analyzeResult.bollinger_bands.position}
                      </span>
                    </p>
                  </div>
                )}

                {/* Fibonacci Levels */}
                {analyzeResult.fibonacci_levels && (
                  <div className="bg-white/5 rounded-lg p-4">
                    <h4 className="text-blue-400 font-semibold mb-3">Fibonacci Retracement Levels</h4>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                      <div className="text-center p-2 bg-white/5 rounded">
                        <p className="text-gray-400 text-xs">High</p>
                        <p className="text-white font-semibold">${analyzeResult.fibonacci_levels.high}</p>
                      </div>
                      <div className="text-center p-2 bg-white/5 rounded">
                        <p className="text-gray-400 text-xs">23.6%</p>
                        <p className="text-white font-semibold">${analyzeResult.fibonacci_levels.fib_236}</p>
                      </div>
                      <div className="text-center p-2 bg-white/5 rounded">
                        <p className="text-gray-400 text-xs">38.2%</p>
                        <p className="text-white font-semibold">${analyzeResult.fibonacci_levels.fib_382}</p>
                      </div>
                      <div className="text-center p-2 bg-yellow-500/20 rounded">
                        <p className="text-yellow-400 text-xs">50%</p>
                        <p className="text-yellow-300 font-semibold">${analyzeResult.fibonacci_levels.fib_50}</p>
                      </div>
                      <div className="text-center p-2 bg-white/5 rounded">
                        <p className="text-gray-400 text-xs">61.8%</p>
                        <p className="text-white font-semibold">${analyzeResult.fibonacci_levels.fib_618}</p>
                      </div>
                      <div className="text-center p-2 bg-white/5 rounded">
                        <p className="text-gray-400 text-xs">78.6%</p>
                        <p className="text-white font-semibold">${analyzeResult.fibonacci_levels.fib_786}</p>
                      </div>
                      <div className="text-center p-2 bg-white/5 rounded">
                        <p className="text-gray-400 text-xs">Low</p>
                        <p className="text-white font-semibold">${analyzeResult.fibonacci_levels.low}</p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Volume */}
                {analyzeResult.indicators && (
                  <div className="bg-white/5 rounded-lg p-4">
                    <h4 className="text-blue-400 font-semibold mb-3">Volume Analysis</h4>
                    <div className="flex justify-between items-center">
                      <div>
                        <p className="text-gray-400 text-sm">Last Volume</p>
                        <p className="text-white font-bold text-xl">{analyzeResult.indicators.last_volume?.toLocaleString() || '-'}</p>
                      </div>
                      <div>
                        <p className="text-gray-400 text-sm">20-Day Average</p>
                        <p className="text-white font-bold text-xl">{analyzeResult.indicators.avg_volume?.toLocaleString() || '-'}</p>
                      </div>
                      <div>
                        {analyzeResult.indicators.volume_spike ? (
                          <span className="px-3 py-2 bg-green-500/30 text-green-300 rounded-lg flex items-center gap-2">
                            <Zap className="w-4 h-4" /> Volume Spike!
                          </span>
                        ) : (
                          <span className="px-3 py-2 bg-gray-500/30 text-gray-300 rounded-lg">Normal Volume</span>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          ) : null}
        </div>
      </div>
    );
  };

  // Pattern Modal
  const PatternModal = () => {
    if (!showPatternModal) return null;

    return (
      <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
        <div className="bg-gradient-to-br from-gray-900 to-gray-800 rounded-2xl p-6 max-w-lg w-full max-h-[90vh] overflow-y-auto border border-blue-500/30">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-white">{selectedSymbol} Pattern Analysis</h2>
            <button onClick={() => setShowPatternModal(false)} className="text-gray-400 hover:text-white">
              <X className="w-6 h-6" />
            </button>
          </div>

          {patternLoading ? (
            <div className="text-center py-8">
              <RefreshCw className="w-8 h-8 text-blue-400 animate-spin mx-auto mb-4" />
              <p className="text-blue-300">Analyzing patterns...</p>
            </div>
          ) : detailedPattern ? (
            <div className="space-y-4">
              {detailedPattern.pattern_details?.length > 0 ? (
                detailedPattern.pattern_details.map((pattern, idx) => (
                  <div key={idx} className="bg-white/5 rounded-lg p-4 border border-white/10">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-lg font-semibold text-white">{pattern.name}</h3>
                      <span className={`px-2 py-1 rounded text-sm ${
                        pattern.signal === 'Buy' || pattern.signal === 'Hold/Buy' ? 'bg-green-500/30 text-green-300' :
                        pattern.signal === 'Sell' || pattern.signal === 'Hold/Sell' ? 'bg-red-500/30 text-red-300' :
                        'bg-yellow-500/30 text-yellow-300'
                      }`}>
                        {pattern.signal}
                      </span>
                    </div>
                    <p className="text-blue-200 text-sm mb-2">{pattern.description}</p>
                    <div className="flex gap-2">
                      <span className="text-xs px-2 py-1 bg-purple-500/20 text-purple-300 rounded">{pattern.type}</span>
                      <span className="text-xs px-2 py-1 bg-blue-500/20 text-blue-300 rounded">{pattern.reliability}</span>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-gray-400 text-center py-4">No specific patterns detected</p>
              )}

              {detailedPattern.support_resistance && (
                <div className="bg-white/5 rounded-lg p-4">
                  <h4 className="text-blue-300 text-sm mb-2">Support & Resistance</h4>
                  <div className="flex justify-between">
                    <div>
                      <p className="text-green-400 text-lg font-bold">${detailedPattern.support_resistance.support}</p>
                      <p className="text-green-300 text-xs">Support</p>
                    </div>
                    <div className="text-right">
                      <p className="text-red-400 text-lg font-bold">${detailedPattern.support_resistance.resistance}</p>
                      <p className="text-red-300 text-xs">Resistance</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-gray-400 text-center py-4">Unable to load pattern data</p>
          )}
        </div>
      </div>
    );
  };

  const filterOptions = [
    { id: 'ema', label: 'EMA Crossover', desc: '50 EMA > 200 EMA', icon: TrendingUp },
    { id: 'fibo', label: 'Fibonacci 50%', desc: 'Price above 50% retracement', icon: BarChart3 },
    { id: 'rsi', label: 'RSI > 50', desc: 'Momentum indicator bullish', icon: Activity },
    { id: 'macd', label: 'MACD > 0', desc: 'MACD line positive', icon: TrendingUp },
    { id: 'volume', label: 'Volume Spike', desc: '2x average volume', icon: Zap }
  ];

  const advancedFilterOptions = [
    { id: 'macd_crossover', label: 'MACD Crossover', desc: 'MACD > Signal', icon: Activity },
    { id: 'rsi_oversold', label: 'RSI Oversold', desc: 'RSI < 30', icon: TrendingUp },
    { id: 'rsi_overbought', label: 'RSI Overbought', desc: 'RSI > 70', icon: TrendingDown },
    { id: 'bb_oversold', label: 'BB Oversold', desc: 'Below lower band', icon: TrendingUp },
    { id: 'bb_overbought', label: 'BB Overbought', desc: 'Above upper band', icon: TrendingDown },
    { id: 'trend_up', label: 'Uptrend', desc: 'Price > EMA20 > EMA50', icon: TrendingUp },
    { id: 'trend_down', label: 'Downtrend', desc: 'Price < EMA20 < EMA50', icon: TrendingDown },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900">
      <AnalyzeModal />
      <PatternModal />

      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl md:text-5xl font-bold text-white mb-4">
            <span className="bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
              NASDAQ Scanner Pro
            </span>
          </h1>
          <p className="text-blue-200 text-lg">Advanced Technical Analysis • Pattern Detection</p>
          <div className="mt-4 flex items-center justify-center gap-2">
            <div className={`w-3 h-3 rounded-full ${backendStatus === 'connected' ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className={`text-sm ${backendStatus === 'connected' ? 'text-green-400' : 'text-red-400'}`}>
              {backendStatus === 'connected' ? 'Backend Connected' : 'Backend Disconnected'}
            </span>
          </div>
        </div>

        {/* FILTERS SECTION - At the top */}
        <div className="bg-white/10 backdrop-blur-md rounded-xl p-6 border border-white/20 mb-8">
          <div className="flex items-center gap-2 mb-4">
            <Filter className="w-6 h-6 text-blue-400" />
            <h2 className="text-2xl font-bold text-white">Technical Filters</h2>
          </div>

          {/* Timeframe */}
          <div className="mb-6">
            <label className="text-blue-300 text-sm mb-2 block font-semibold">Timeframe:</label>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="radio" name="timeframe" value="1d" checked={timeframe === '1d'} onChange={(e) => setTimeframe(e.target.value)} className="accent-blue-500 w-4 h-4" />
                <span className="text-white">Daily</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="radio" name="timeframe" value="1wk" checked={timeframe === '1wk'} onChange={(e) => setTimeframe(e.target.value)} className="accent-blue-500 w-4 h-4" />
                <span className="text-white">Weekly</span>
              </label>
            </div>
          </div>

          {/* Basic Filters */}
          <div className="mb-6">
            <label className="text-blue-300 text-sm mb-3 block font-semibold">Basic Filters:</label>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
              {filterOptions.map(option => {
                const Icon = option.icon;
                return (
                  <button
                    key={option.id}
                    onClick={() => handleFilterChange(option.id)}
                    className={`p-4 rounded-lg border-2 transition-all ${
                      filters[option.id] ? 'bg-blue-500 border-blue-400 shadow-lg shadow-blue-500/50' : 'bg-white/5 border-white/20 hover:border-blue-400/50'
                    }`}
                  >
                    <Icon className={`w-6 h-6 mb-2 ${filters[option.id] ? 'text-white' : 'text-blue-300'}`} />
                    <div className={`font-semibold mb-1 text-sm ${filters[option.id] ? 'text-white' : 'text-blue-100'}`}>{option.label}</div>
                    <div className={`text-xs ${filters[option.id] ? 'text-blue-100' : 'text-blue-300'}`}>{option.desc}</div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Advanced Filters */}
          <div>
            <label className="text-green-300 text-sm mb-3 block font-semibold">Advanced Filters (for single stock analysis):</label>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
              {advancedFilterOptions.map(option => {
                const Icon = option.icon;
                return (
                  <button
                    key={option.id}
                    onClick={() => handleAdvancedFilterChange(option.id)}
                    className={`p-3 rounded-lg border transition-all ${
                      advancedFilters[option.id] ? 'bg-green-500/30 border-green-400' : 'bg-white/5 border-white/20 hover:border-green-400/50'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <Icon className={`w-4 h-4 ${advancedFilters[option.id] ? 'text-green-300' : 'text-gray-400'}`} />
                      <span className={`text-xs font-semibold ${advancedFilters[option.id] ? 'text-green-200' : 'text-white'}`}>{option.label}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* SEARCH OPTIONS - Two columns */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          
          {/* Search Single Stock */}
          <div className="bg-gradient-to-r from-green-500/10 to-emerald-500/10 backdrop-blur-md rounded-xl p-6 border border-green-500/30">
            <div className="flex items-center gap-2 mb-4">
              <Search className="w-6 h-6 text-green-400" />
              <h2 className="text-xl font-bold text-white">Search Single Stock</h2>
            </div>
            
            <form onSubmit={handleSearchSubmit}>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Enter symbol (AAPL, TSLA...)"
                    className="w-full bg-white/5 border border-white/20 rounded-lg px-4 py-3 text-white placeholder-green-300/50 focus:outline-none focus:border-green-400"
                  />
                  {searchLoading && <RefreshCw className="absolute right-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-green-400 animate-spin" />}
                  
                  {showSearchResults && searchResults.length > 0 && (
                    <div className="absolute top-full left-0 right-0 mt-1 bg-gray-800 border border-white/20 rounded-lg shadow-xl z-50 max-h-60 overflow-y-auto">
                      {searchResults.map((stock, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => handleAnalyzeStock(stock.symbol)}
                          className="w-full px-4 py-3 text-left hover:bg-white/10 border-b border-white/10 last:border-b-0"
                        >
                          <span className="text-white font-bold">{stock.symbol}</span>
                          <span className="text-green-300 ml-2 text-sm">{stock.name}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <button
                  type="submit"
                  disabled={!searchQuery.trim() || analyzeLoading}
                  className="bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 disabled:from-gray-500 disabled:to-gray-600 text-white font-semibold px-6 py-3 rounded-lg flex items-center gap-2"
                >
                  <Search className="w-5 h-5" />
                  Analyze
                </button>
              </div>
              <p className="text-green-300/70 text-xs mt-2">
                Analyzes stock with all selected filters (basic + advanced) and shows patterns
              </p>
            </form>
          </div>

          {/* Scan All Stocks */}
          <div className="bg-gradient-to-r from-blue-500/10 to-indigo-500/10 backdrop-blur-md rounded-xl p-6 border border-blue-500/30">
            <div className="flex items-center gap-2 mb-4">
              <BarChart3 className="w-6 h-6 text-blue-400" />
              <h2 className="text-xl font-bold text-white">Scan All NASDAQ Stocks</h2>
            </div>

            <button
              onClick={handleScan}
              disabled={loading}
              className="w-full bg-gradient-to-r from-blue-500 to-indigo-500 hover:from-blue-600 hover:to-indigo-600 disabled:from-gray-500 disabled:to-gray-600 text-white font-semibold py-3 rounded-lg flex items-center justify-center gap-2 shadow-lg"
            >
              <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
              {loading ? 'Scanning...' : `Scan All Stocks (${timeframe === '1d' ? 'Daily' : 'Weekly'})`}
            </button>
            
            <p className="text-blue-300/70 text-xs mt-2">
              Scans 100+ stocks using basic filters only. Click a result to see patterns.
            </p>
            
            {loading && (
              <div className="mt-4">
                <div className="bg-white/10 rounded-full h-2 overflow-hidden">
                  <div className="bg-gradient-to-r from-blue-500 to-indigo-500 h-full animate-pulse w-full" />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 mb-6">
            <div className="flex items-center gap-2 text-red-300">
              <AlertCircle className="w-5 h-5" />
              <div className="font-semibold">{error}</div>
            </div>
          </div>
        )}

        {/* Scan Time */}
        {scanTime && (
          <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4 mb-6">
            <div className="text-green-300 text-sm">
              Scan completed in <strong>{scanTime}s</strong> • Found <strong>{results.length}</strong> matches • Timeframe: <strong>{timeframe === '1d' ? 'Daily' : 'Weekly'}</strong>
            </div>
          </div>
        )}

        {/* Results Table - Detailed like before */}
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
                    {filters.volume && <th className="pb-3 text-blue-300 font-semibold">Volume</th>}
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

        {/* Empty State */}
        {!loading && results.length === 0 && !error && (
          <div className="bg-white/5 backdrop-blur-md rounded-xl p-12 border border-white/10 text-center">
            <BarChart3 className="w-16 h-16 text-blue-400 mx-auto mb-4" />
            <h3 className="text-xl font-bold text-white mb-2">Ready to Analyze</h3>
            <p className="text-blue-300">
              Select filters above, then use <span className="text-green-400 font-semibold">Search Single Stock</span> or <span className="text-blue-400 font-semibold">Scan All Stocks</span>
            </p>
          </div>
        )}
      </div>

      <footer className="bg-black/30 border-t border-blue-500/30 mt-12 py-8">
        <div className="container mx-auto px-4 text-center text-blue-300 text-sm">
          <p>NASDAQ Scanner Pro © 2026 • Educational Tool • Not Financial Advice</p>
        </div>
      </footer>
    </div>
  );
};

export default NasdaqScanner;