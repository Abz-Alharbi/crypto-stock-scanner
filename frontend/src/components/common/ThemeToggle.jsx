import { Sun, Moon } from 'lucide-react';
import useThemeStore from '../../store/useThemeStore';

export default function ThemeToggle() {
  const { theme, toggleTheme } = useThemeStore();
  const isDark = theme === 'dark';

  return (
    <button
      onClick={toggleTheme}
      className="relative flex items-center justify-center w-9 h-9 rounded-xl transition-all duration-300 hover:scale-105 active:scale-95"
      style={{
        background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
        border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}`,
      }}
      title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
      aria-label={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
    >
      <div
        className="transition-all duration-300"
        style={{
          transform: isDark ? 'rotate(0deg) scale(1)' : 'rotate(180deg) scale(0)',
          opacity: isDark ? 1 : 0,
          position: 'absolute',
        }}
      >
        <Moon size={16} className="text-scanner-accent" />
      </div>
      <div
        className="transition-all duration-300"
        style={{
          transform: isDark ? 'rotate(-180deg) scale(0)' : 'rotate(0deg) scale(1)',
          opacity: isDark ? 0 : 1,
          position: 'absolute',
        }}
      >
        <Sun size={16} style={{ color: '#f59e0b' }} />
      </div>
    </button>
  );
}
