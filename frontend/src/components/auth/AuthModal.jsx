import React, { useState } from 'react';
import { X, Eye, EyeOff, LogIn, UserPlus, AlertCircle } from 'lucide-react';
import useAuthStore from '../../store/useAuthStore';

export default function AuthModal() {
  const { showAuthModal, authMode, setAuthModal, login, register, isLoading, error } = useAuthStore();
  const [form, setForm] = useState({ username: '', email: '', password: '', confirmPassword: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState('');

  if (!showAuthModal) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLocalError('');

    if (authMode === 'register') {
      if (!form.username.trim()) return setLocalError('Username is required');
      if (form.password !== form.confirmPassword) return setLocalError('Passwords do not match');
      if (form.password.length < 6) return setLocalError('Password must be at least 6 characters');
      try { await register(form.username.trim(), form.email.trim(), form.password); } catch {}
    } else {
      try { await login(form.email.trim(), form.password); } catch {}
    }
  };

  const displayError = localError || error;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in" onClick={() => setAuthModal(false)}>
      <div className="w-full max-w-md bg-scanner-card border border-scanner-border rounded-2xl shadow-2xl animate-slide-up" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-scanner-border">
          <div>
            <h2 className="font-display text-xl font-bold">{authMode === 'login' ? 'Welcome Back' : 'Create Account'}</h2>
            <p className="text-sm text-scanner-text-dim mt-1">
              {authMode === 'login' ? 'Sign in to your account' : 'Start scanning the markets'}
            </p>
          </div>
          <button onClick={() => setAuthModal(false)} className="p-2 rounded-lg hover:bg-scanner-bg transition-colors">
            <X size={18} className="text-scanner-text-dim" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {displayError && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-scanner-danger/10 border border-scanner-danger/30 text-scanner-danger text-sm">
              <AlertCircle size={16} /> {displayError}
            </div>
          )}

          {authMode === 'register' && (
            <div>
              <label className="block text-xs font-medium text-scanner-text-dim mb-1.5 uppercase tracking-wider">Username</label>
              <input
                type="text" value={form.username}
                onChange={e => setForm({ ...form, username: e.target.value })}
                className="w-full px-4 py-2.5 bg-scanner-bg border border-scanner-border rounded-lg text-sm focus:outline-none focus:border-scanner-accent transition-colors"
                placeholder="Choose a username"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-scanner-text-dim mb-1.5 uppercase tracking-wider">Email</label>
            <input
              type="email" value={form.email}
              onChange={e => setForm({ ...form, email: e.target.value })}
              className="w-full px-4 py-2.5 bg-scanner-bg border border-scanner-border rounded-lg text-sm focus:outline-none focus:border-scanner-accent transition-colors"
              placeholder="your@email.com"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-scanner-text-dim mb-1.5 uppercase tracking-wider">Password</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'} value={form.password}
                onChange={e => setForm({ ...form, password: e.target.value })}
                className="w-full px-4 py-2.5 bg-scanner-bg border border-scanner-border rounded-lg text-sm focus:outline-none focus:border-scanner-accent transition-colors pr-10"
                placeholder="••••••••"
                required
              />
              <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-scanner-text-dim hover:text-scanner-text">
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {authMode === 'register' && (
            <div>
              <label className="block text-xs font-medium text-scanner-text-dim mb-1.5 uppercase tracking-wider">Confirm Password</label>
              <input
                type="password" value={form.confirmPassword}
                onChange={e => setForm({ ...form, confirmPassword: e.target.value })}
                className="w-full px-4 py-2.5 bg-scanner-bg border border-scanner-border rounded-lg text-sm focus:outline-none focus:border-scanner-accent transition-colors"
                placeholder="••••••••"
                required
              />
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 py-3 rounded-lg bg-scanner-accent text-scanner-bg font-semibold text-sm hover:bg-scanner-accent/90 transition-all shadow-lg shadow-scanner-accent/20 disabled:opacity-50"
          >
            {isLoading ? (
              <div className="w-4 h-4 border-2 border-scanner-bg border-t-transparent rounded-full animate-spin" />
            ) : authMode === 'login' ? (
              <><LogIn size={16} /> Sign In</>
            ) : (
              <><UserPlus size={16} /> Create Account</>
            )}
          </button>
        </form>

        {/* Toggle mode */}
        <div className="p-6 pt-0 text-center">
          <p className="text-sm text-scanner-text-dim">
            {authMode === 'login' ? "Don't have an account?" : 'Already have an account?'}{' '}
            <button
              onClick={() => { setAuthModal(true, authMode === 'login' ? 'register' : 'login'); setLocalError(''); }}
              className="text-scanner-accent font-medium hover:underline"
            >
              {authMode === 'login' ? 'Sign up' : 'Sign in'}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
