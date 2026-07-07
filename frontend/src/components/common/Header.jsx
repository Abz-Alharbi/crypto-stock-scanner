import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Activity, TrendingUp, LogIn, LogOut, Settings, Menu, X, BookmarkPlus, Newspaper, PieChart, Bell } from 'lucide-react';
import useAuthStore, { AUTH_DISABLED } from '../../store/useAuthStore';
import useMarketStore from '../../store/useMarketStore';
import ThemeToggle from './ThemeToggle';

export default function Header() {
  const { user, isAuthenticated, logout, setAuthModal } = useAuthStore();
  const {
    activeMarket,
    setMarket,
    isConnected,
    notifications,
    unreadNotificationCount,
    loadNotifications,
    markNotificationRead,
  } = useMarketStore();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      loadNotifications();
    }
  }, [isAuthenticated, loadNotifications]);

  const navItems = [
    { key: 'scanner', label: 'Scanner', icon: Activity, path: '/', active: (path) => path === '/' },
    { key: 'news', label: 'News', icon: Newspaper, path: '/news', active: (path) => path.startsWith('/news') },
    { key: 'fundamentals', label: 'Fundamentals', icon: PieChart, path: '/fundamentals/AAPL', active: (path) => path.startsWith('/fundamentals') },
    { key: 'watchlist', label: 'Watchlist', icon: BookmarkPlus, path: '/watchlist', active: (path) => path.startsWith('/watchlist') },
  ];

  if (user?.role === 'admin') {
    navItems.push({ key: 'admin', label: 'Admin', icon: Settings, path: '/admin', active: (path) => path.startsWith('/admin') });
  }

  const goTo = (path) => {
    navigate(path);
    setMobileMenuOpen(false);
  };

  return (
    <header className="glass gradient-border sticky top-0 z-40">
      <div className="max-w-[1600px] mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => goTo('/')}>
            <div className="relative">
              <div className="w-9 h-9 bg-gradient-to-br from-scanner-accent to-emerald-600 rounded-lg flex items-center justify-center">
                <TrendingUp size={20} className="text-scanner-bg" />
              </div>
              <div className={`absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-scanner-bg ${isConnected ? 'bg-scanner-accent pulse-dot' : 'bg-scanner-danger'}`} />
            </div>
            <div className="hidden sm:block">
              <h1 className="font-display font-bold text-lg leading-none tracking-tight">Market Scanner</h1>
              <p className="text-[10px] text-scanner-accent font-mono uppercase tracking-widest">Pro</p>
            </div>
          </div>

          {/* Market Toggle */}
          <div className="hidden md:flex items-center bg-scanner-bg/60 rounded-lg p-0.5 border border-scanner-border">
            {['stocks', 'crypto'].map((m) => (
              <button
                key={m}
                onClick={() => setMarket(m)}
                className={`px-4 py-1.5 text-xs font-semibold uppercase tracking-wider rounded-md transition-all duration-200 ${
                  activeMarket === m
                    ? 'bg-scanner-accent text-scanner-bg shadow-lg shadow-scanner-accent/20'
                    : 'text-scanner-text-dim hover:text-scanner-text'
                }`}
              >
                {m === 'stocks' ? '📊 Stocks' : '₿ Crypto'}
              </button>
            ))}
          </div>

          {/* Nav items */}
          <nav className="hidden md:flex items-center gap-1">
            {navItems.map(({ key, label, icon: Icon, path, active }) => (
              <button
                key={key}
                onClick={() => goTo(path)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                  active(location.pathname)
                    ? 'bg-scanner-accent/10 text-scanner-accent'
                    : 'text-scanner-text-dim hover:text-scanner-text hover:bg-scanner-card'
                }`}
              >
                <Icon size={16} />
                {label}
              </button>
            ))}
          </nav>

          {/* Theme Toggle + Auth + Mobile menu */}
          <div className="flex items-center gap-2">
            <ThemeToggle />

            {isAuthenticated && (
              <div className="relative">
                <button
                  onClick={() => setNotificationsOpen(!notificationsOpen)}
                  className="relative p-2 rounded-lg bg-scanner-card border border-scanner-border hover:border-scanner-accent/30 text-scanner-text-dim hover:text-scanner-accent transition-all"
                  title="Notifications"
                  aria-label="Notifications"
                >
                  <Bell size={16} />
                  {unreadNotificationCount > 0 && (
                    <span className="absolute -top-1 -right-1 min-w-4 h-4 px-1 rounded-full bg-scanner-danger text-[9px] font-bold text-white flex items-center justify-center">
                      {unreadNotificationCount}
                    </span>
                  )}
                </button>

                {notificationsOpen && (
                  <div className="absolute right-0 mt-2 w-80 max-w-[calc(100vw-2rem)] bg-scanner-card border border-scanner-border rounded-xl shadow-2xl py-2 animate-slide-down">
                    <div className="px-4 py-2 border-b border-scanner-border">
                      <p className="text-xs font-semibold uppercase tracking-widest text-scanner-text-dim">Notifications</p>
                    </div>
                    <div className="max-h-80 overflow-y-auto">
                      {notifications.length === 0 ? (
                        <p className="px-4 py-6 text-center text-sm text-scanner-text-dim">No notifications yet.</p>
                      ) : notifications.map((notification) => (
                        <button
                          key={notification.id}
                          onClick={() => markNotificationRead(notification.id)}
                          className={`w-full px-4 py-3 text-left border-b border-scanner-border/50 last:border-b-0 hover:bg-scanner-bg/50 transition-colors ${
                            notification.is_read ? 'opacity-70' : ''
                          }`}
                        >
                          <div className="flex items-start gap-2">
                            {!notification.is_read && <span className="mt-1.5 h-2 w-2 rounded-full bg-scanner-accent flex-shrink-0" />}
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-scanner-text truncate">{notification.title}</p>
                              <p className="mt-1 text-xs text-scanner-text-dim line-clamp-2">{notification.message}</p>
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {isAuthenticated ? (
              <div className="relative">
                <button
                  onClick={() => setProfileOpen(!profileOpen)}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-scanner-card border border-scanner-border hover:border-scanner-accent/30 transition-all"
                >
                  <div className="w-6 h-6 rounded-full bg-gradient-to-br from-scanner-accent to-emerald-600 flex items-center justify-center">
                    <span className="text-[10px] font-bold text-scanner-bg">{user?.username?.[0]?.toUpperCase()}</span>
                  </div>
                  <span className="hidden sm:block text-sm text-scanner-text">{user?.username}</span>
                </button>

                {profileOpen && (
                  <div className="absolute right-0 mt-2 w-48 bg-scanner-card border border-scanner-border rounded-xl shadow-2xl py-2 animate-slide-down">
                    <div className="px-4 py-2 border-b border-scanner-border">
                      <p className="text-xs text-scanner-text-dim">Signed in as</p>
                      <p className="text-sm font-medium truncate">{user?.email}</p>
                      <span className="inline-block mt-1 text-[10px] px-2 py-0.5 rounded-full bg-scanner-accent/10 text-scanner-accent uppercase">{user?.plan} plan</span>
                    </div>
                    {/* # RE-ENABLE AUTH: remove this block */}
                    {!AUTH_DISABLED && (
                      <button
                        onClick={() => { logout(); setProfileOpen(false); }}
                        className="w-full flex items-center gap-2 px-4 py-2 text-sm text-scanner-danger hover:bg-scanner-danger/10 transition-colors"
                      >
                        <LogOut size={14} /> Sign out
                      </button>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <>
                {/* # RE-ENABLE AUTH: remove this block */}
                {!AUTH_DISABLED && (
                  <button
                    onClick={() => setAuthModal(true, 'login')}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-scanner-accent text-scanner-bg text-sm font-semibold hover:bg-scanner-accent/90 transition-all shadow-lg shadow-scanner-accent/20"
                  >
                    <LogIn size={14} /> Sign In
                  </button>
                )}
              </>
            )}

            <button
              className="md:hidden p-2 rounded-lg hover:bg-scanner-card"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-scanner-border py-3 space-y-1 animate-slide-down">
            <div className="flex gap-2 mb-3">
              {['stocks', 'crypto'].map((m) => (
                <button
                  key={m}
                  onClick={() => { setMarket(m); setMobileMenuOpen(false); }}
                  className={`flex-1 px-3 py-2 text-xs font-semibold uppercase tracking-wider rounded-lg transition-all ${
                    activeMarket === m ? 'bg-scanner-accent text-scanner-bg' : 'bg-scanner-card text-scanner-text-dim'
                  }`}
                >
                  {m === 'stocks' ? '📊 Stocks' : '₿ Crypto'}
                </button>
              ))}
            </div>
            {navItems.map(({ key, label, icon: Icon, path, active }) => (
              <button
                key={key}
                onClick={() => goTo(path)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm ${
                  active(location.pathname) ? 'bg-scanner-accent/10 text-scanner-accent' : 'text-scanner-text-dim hover:bg-scanner-card'
                }`}
              >
                <Icon size={16} /> {label}
              </button>
            ))}
          </div>
        )}
      </div>
    </header>
  );
}
