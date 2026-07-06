import React, { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { Activity, Wifi, WifiOff } from 'lucide-react';
import Header from './components/common/Header';
import SearchBar from './components/common/SearchBar';
import FilterPanel from './components/filters/FilterPanel';
import ScanResults from './components/stock/ScanResults';
import WatchlistPage from './components/stock/WatchlistPage';
import AuthModal from './components/auth/AuthModal';
import RouteErrorBoundary from './components/common/RouteErrorBoundary';
import useMarketStore from './store/useMarketStore';
import useAuthStore from './store/useAuthStore';
import useThemeStore from './store/useThemeStore';

const AdminPanel = lazy(() => import('./components/admin/AdminPanel'));
const NewsRoom = lazy(() => import('./components/news/NewsRoom'));
const FundamentalAnalysis = lazy(() => import('./components/fundamentals/FundamentalAnalysis'));
const StockDetailModal = lazy(() => import('./components/stock/StockDetailModal'));

function AuthRequired({ children, adminOnly = false }) {
  const location = useLocation();
  const { isAuthenticated, user, setAuthModal } = useAuthStore();

  useEffect(() => {
    if (!isAuthenticated) {
      sessionStorage.setItem('pending_auth_path', `${location.pathname}${location.search}`);
      setAuthModal(true, 'login');
    }
  }, [isAuthenticated, location.pathname, location.search, setAuthModal]);

  if (!isAuthenticated) return <Navigate to="/" replace />;

  if (adminOnly && !user) {
    return (
      <div className="bg-scanner-card border border-scanner-border rounded-2xl p-12 text-center">
        <h3 className="font-display text-xl font-bold">Checking Access</h3>
        <p className="text-sm text-scanner-text-dim mt-2">Verifying your session.</p>
      </div>
    );
  }

  if (adminOnly && user?.role !== 'admin') {
    return (
      <div className="bg-scanner-card border border-scanner-danger/30 rounded-2xl p-12 text-center">
        <h3 className="font-display text-xl font-bold text-scanner-danger">Admin Access Required</h3>
        <p className="text-sm text-scanner-text-dim mt-2">Your account does not have permission to view this page.</p>
      </div>
    );
  }

  return children;
}

function RouteFrame({ children }) {
  const location = useLocation();
  return (
    <RouteErrorBoundary key={location.pathname}>
      {children}
    </RouteErrorBoundary>
  );
}

function RouteLoading({ label = 'Loading page...' }) {
  return (
    <div className="flex items-center justify-center rounded-2xl border border-scanner-border bg-scanner-card p-12 text-sm text-scanner-text-dim">
      {label}
    </div>
  );
}

function LazyRoute({ children, label }) {
  return (
    <Suspense fallback={<RouteLoading label={label} />}>
      {children}
    </Suspense>
  );
}

function ScannerPage() {
  return (
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
  );
}

function WatchlistRoutePage() {
  return (
    <div className="max-w-3xl mx-auto">
      <h2 className="font-display text-2xl font-bold mb-6">Your Watchlist</h2>
      <WatchlistPage />
    </div>
  );
}

function AdminRoutePage() {
  return (
    <div>
      <h2 className="font-display text-2xl font-bold mb-6 flex items-center gap-2">
        <Activity size={24} className="text-scanner-accent" />
        Admin Panel
      </h2>
      <AdminPanel />
    </div>
  );
}

function AppShell() {
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

      <Header />
      <AuthModal />
      <Suspense fallback={null}>
        <StockDetailModal />
      </Suspense>

      <main className="flex-1 relative z-10">
        <div className="max-w-[1600px] mx-auto px-4 sm:px-6 py-6">
          {!isConnected && (
            <div className="mb-4 flex items-center gap-3 p-3 rounded-xl bg-scanner-danger/10 border border-scanner-danger/30 text-scanner-danger text-sm animate-fade-in">
              <WifiOff size={16} />
              <span>Cannot connect to backend. Make sure the Flask server is running on port 5000.</span>
            </div>
          )}

          <Routes>
            <Route path="/" element={<RouteFrame><ScannerPage /></RouteFrame>} />
            <Route
              path="/watchlist"
              element={<RouteFrame><AuthRequired><WatchlistRoutePage /></AuthRequired></RouteFrame>}
            />
            <Route
              path="/news"
              element={<RouteFrame><AuthRequired><LazyRoute label="Loading news..."><NewsRoom /></LazyRoute></AuthRequired></RouteFrame>}
            />
            <Route
              path="/fundamentals/:symbol"
              element={<RouteFrame><AuthRequired><LazyRoute label="Loading fundamentals..."><FundamentalAnalysis /></LazyRoute></AuthRequired></RouteFrame>}
            />
            <Route
              path="/admin"
              element={<RouteFrame><AuthRequired adminOnly><LazyRoute label="Loading admin panel..."><AdminRoutePage /></LazyRoute></AuthRequired></RouteFrame>}
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </main>

      <footer className="border-t border-scanner-border py-6 mt-auto">
        <div className="max-w-[1600px] mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-xs text-scanner-text-dim">
            Market Scanner Pro &copy; {new Date().getFullYear()} â€” Technical analysis for educational purposes only
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
            <span>âš ï¸ Not financial advice</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AppShell />
    </BrowserRouter>
  );
}
