import { create } from 'zustand';
import { authAPI, setUnauthorizedHandler } from '../services/api';

const ACCESS_TOKEN_KEY = 'access_token';
const USER_KEY = 'auth_user';
export const AUTH_DISABLED = String(import.meta.env.VITE_AUTH_DISABLED).toLowerCase() === 'true';
export const MOCK_AUTH_USER = {
  id: 1,
  username: 'test',
  email: 'test@test.com',
  role: 'admin',
  plan: 'pro',
};

// # RE-ENABLE AUTH: remove this block
if (AUTH_DISABLED) {
  localStorage.setItem(ACCESS_TOKEN_KEY, 'auth-disabled');
  localStorage.setItem(USER_KEY, JSON.stringify(MOCK_AUTH_USER));
}

const useAuthStore = create((set, get) => ({
  user: AUTH_DISABLED ? MOCK_AUTH_USER : JSON.parse(localStorage.getItem(USER_KEY) || 'null'),
  token: AUTH_DISABLED ? 'auth-disabled' : localStorage.getItem(ACCESS_TOKEN_KEY) || null,
  isAuthenticated: AUTH_DISABLED || !!localStorage.getItem(ACCESS_TOKEN_KEY),
  isLoading: false,
  error: null,
  showAuthModal: false,
  authMode: 'login', // login or register

  setAuthModal: (show, mode = 'login') => {
    // # RE-ENABLE AUTH: remove this block
    if (AUTH_DISABLED) return;
    set({ showAuthModal: show, authMode: mode, error: null });
  },

  login: async (email, password) => {
    set({ isLoading: true, error: null });
    try {
      const { data } = await authAPI.login({ email, password });
      const token = data.access_token || data.token;
      localStorage.setItem(ACCESS_TOKEN_KEY, token);
      localStorage.setItem(USER_KEY, JSON.stringify(data.user));
      set({ user: data.user, token, isAuthenticated: true, isLoading: false, showAuthModal: false });
      return data.user;
    } catch (err) {
      const msg = err.response?.data?.error || 'Login failed';
      set({ error: msg, isLoading: false });
      throw new Error(msg);
    }
  },

  register: async (username, email, password) => {
    set({ isLoading: true, error: null });
    try {
      const { data } = await authAPI.register({ username, email, password });
      const token = data.access_token || data.token;
      localStorage.setItem(ACCESS_TOKEN_KEY, token);
      localStorage.setItem(USER_KEY, JSON.stringify(data.user));
      set({ user: data.user, token, isAuthenticated: true, isLoading: false, showAuthModal: false });
      return data.user;
    } catch (err) {
      const msg = err.response?.data?.error || 'Registration failed';
      set({ error: msg, isLoading: false });
      throw new Error(msg);
    }
  },

  logout: () => {
    // # RE-ENABLE AUTH: remove this block
    if (AUTH_DISABLED) {
      set({ user: MOCK_AUTH_USER, token: 'auth-disabled', isAuthenticated: true, showAuthModal: false });
      return;
    }
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    set({ user: null, token: null, isAuthenticated: false });
  },

  checkAuth: async () => {
    // # RE-ENABLE AUTH: remove this block
    if (AUTH_DISABLED) {
      localStorage.setItem(ACCESS_TOKEN_KEY, 'auth-disabled');
      localStorage.setItem(USER_KEY, JSON.stringify(MOCK_AUTH_USER));
      set({ user: MOCK_AUTH_USER, token: 'auth-disabled', isAuthenticated: true, showAuthModal: false });
      return;
    }
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    try {
      const { data } = await authAPI.me();
      set({ user: data.user, token, isAuthenticated: true });
    } catch {
      localStorage.removeItem(ACCESS_TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      set({ user: null, token: null, isAuthenticated: false });
    }
  }
}));

setUnauthorizedHandler(() => {
  // # RE-ENABLE AUTH: remove this block
  if (AUTH_DISABLED) {
    useAuthStore.setState({
      user: MOCK_AUTH_USER,
      token: 'auth-disabled',
      isAuthenticated: true,
      showAuthModal: false,
      authMode: 'login',
      error: null,
    });
    return;
  }
  useAuthStore.setState({
    user: null,
    token: null,
    isAuthenticated: false,
    showAuthModal: true,
    authMode: 'login',
    error: null,
  });
});

export default useAuthStore;
