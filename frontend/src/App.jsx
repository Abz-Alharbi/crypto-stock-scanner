import React, { useEffect, useState } from 'react';
import { Toaster } from 'react-hot-toast';
import Header from './components/common/Header';
import SearchBar from './components/common/SearchBar';
import FilterPanel from './components/filters/FilterPanel';
import ScanResults from './components/stock/ScanResults';
import StockDetailModal from './components/stock/StockDetailModal';
import WatchlistPage from './components/stock/WatchlistPage';
import NewsRoom from './components/news/NewsRoom';
import FundamentalAnalysis from './components/fundamentals/FundamentalAnalysis';
import AuthModal from './components/auth/AuthModal';
import AdminPanel from './components/admin/AdminPanel';
import useMarketStore from './store/useMarketStore';
import useAuthStore from './store/useAuthStore';
import useThemeStore from './store/useThemeStore';
import { Activity, Wifi, WifiOff } from 'lucide-react';

export default function App() {
  const [currentPage, setCurrentPage] = useState('scanner');
  const { checkConnection, loadFilters, isConnected, apiStatus } = useMarketStore();
  const { checkAuth } = useAuthStore();
  const { theme, initTheme } = useThemeStore();

  useEffect(() => {
    initTheme();
    checkAuth();
    checkConnection();
    loadFilters();
    const interval = setInterval(checkConnection, 60000);
    return () => clearInterval(interval);
  }, []);

  const isDark = theme === 'dark';

  return (
    <div className="noise-bg min-h-screen flex flex-col">
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: isDark ? '#1a1f2e' : '#ffffff',
            color: isDark ? '#e5e7eb' : '#1a1f2e',
            border: `1px solid ${isDark ? '#2a3144' : '#e2e5ea'}`,
            fontSize: '13px',
          },
          success: { iconTheme: { primary: isDark ? '#00d4aa' : '#059669', secondary: isDark ? '#0a0e17' : '#ffffff' } },
          error: { iconTheme: { primary: '#ef4444', secondary: isDark ? '#0a0e17' : '#ffffff' } },
        }}
      />

      <Header currentPage={currentPage} setCurrentPage={setCurrentPage} />
      <AuthModal />
      <StockDetailModal />

      <main className="flex-1 relative z-10">
        <div className="max-w-[1600px] mx-auto px-4 sm:px-6 py-6">
          {/* Connection Banner */}
          {!isConnected && (
            <div className="mb-4 flex items-center gap-3 p-3 rounded-xl bg-scanner-danger/10 border border-scanner-danger/30 text-scanner-danger text-sm animate-fade-in">
              <WifiOff size={16} />
              <span>Cannot connect to backend. Make sure the Flask server is running on port 5000.</span>
            </div>
          )}

          {/* Scanner Page */}
          {currentPage === 'scanner' && (
            <>
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-6">
                <div>
                  <h2 className="font-display text-2xl font-bold flex items-center gap-2">
                    <Activity size={24} className="text-scanner-accent" />
                    Market Scanner
                  </h2>
                  <p className="text-sm text-scanner-text-dim mt-1">
                    Scan US stocks & crypto with advanced technical analysis filters
                  </p>
                </div>
                <SearchBar />
              </div>
              <div className="flex flex-col lg:flex-row gap-6">
                <aside className="lg:w-80 xl:w-96 flex-shrink-0">
                  <div className="lg:sticky lg:top-20">
                    <FilterPanel />
                  </div>
                </aside>
                <section className="flex-1 min-w-0">
                  <ScanResults />
                </section>
              </div>
            </>
          )}

          {/* Newsroom Page */}
          {currentPage === 'newsroom' && <NewsRoom />}

          {/* Fundamentals Page */}
          {currentPage === 'fundamentals' && <FundamentalAnalysis />}

          {/* Watchlist Page */}
          {currentPage === 'watchlist' && (
            <div className="max-w-3xl mx-auto">
              <h2 className="font-display text-2xl font-bold mb-6">Your Watchlist</h2>
              <WatchlistPage />
            </div>
          )}

          {/* Admin Page */}
          {currentPage === 'admin' && (
            <div>
              <h2 className="font-display text-2xl font-bold mb-6 flex items-center gap-2">
                <Activity size={24} className="text-scanner-accent" />
                Admin Panel
              </h2>
              <AdminPanel />
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-scanner-border py-6 mt-auto">
        <div className="max-w-[1600px] mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-xs text-scanner-text-dim">
            Market Scanner Pro &copy; {new Date().getFullYear()} — Technical analysis for educational purposes only
          </p>
          <div className="flex items-center gap-4 text-xs text-scanner-text-dim">
            <div className="flex items-center gap-1.5">
              {isConnected ? (
                <><Wifi size={12} className="text-scanner-accent" /> <span className="text-scanner-accent">API Connected</span></>
              ) : (
                <><WifiOff size={12} className="text-scanner-danger" /> <span className="text-scanner-danger">Disconnected</span></>
              )}
            </div>
            {apiStatus && (
              <span>Stocks: {apiStatus.stock_symbols} | Crypto: {apiStatus.crypto_symbols}</span>
            )}
            <span>⚠️ Not financial advice</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
