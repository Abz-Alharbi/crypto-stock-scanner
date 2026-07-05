import { create } from 'zustand';

const useThemeStore = create((set) => ({
  theme: localStorage.getItem('scanner-theme') || 'dark',

  setTheme: (theme) => {
    localStorage.setItem('scanner-theme', theme);
    document.documentElement.setAttribute('data-theme', theme);
    // Add transition class briefly for smooth color change
    document.documentElement.classList.add('theme-transition');
    setTimeout(() => document.documentElement.classList.remove('theme-transition'), 400);
    set({ theme });
  },

  toggleTheme: () => {
    const current = localStorage.getItem('scanner-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    localStorage.setItem('scanner-theme', next);
    document.documentElement.setAttribute('data-theme', next);
    document.documentElement.classList.add('theme-transition');
    setTimeout(() => document.documentElement.classList.remove('theme-transition'), 400);
    set({ theme: next });
  },

  // Call on app init to apply saved theme
  initTheme: () => {
    const saved = localStorage.getItem('scanner-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    set({ theme: saved });
  },
}));

export default useThemeStore;
