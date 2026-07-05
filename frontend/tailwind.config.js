/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        scanner: {
          bg: 'var(--color-bg)',
          surface: 'var(--color-surface)',
          card: 'var(--color-card)',
          border: 'var(--color-border)',
          accent: 'var(--color-accent)',
          'accent-dim': 'var(--color-accent-dim)',
          warning: 'var(--color-warning)',
          danger: 'var(--color-danger)',
          bullish: 'var(--color-bullish)',
          bearish: 'var(--color-bearish)',
          neutral: 'var(--color-neutral)',
          text: 'var(--color-text)',
          'text-dim': 'var(--color-text-dim)',
          'text-muted': 'var(--color-text-muted)',
        }
      },
      fontFamily: {
        sans: ['"DM Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
        display: ['"Outfit"', '"DM Sans"', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'scanner-sm': 'var(--shadow-sm)',
        'scanner-md': 'var(--shadow-md)',
        'scanner-lg': 'var(--shadow-lg)',
      },
      animation: {
        'pulse-slow': 'pulse 3s ease-in-out infinite',
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        fadeIn: { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        slideUp: { '0%': { transform: 'translateY(10px)', opacity: '0' }, '100%': { transform: 'translateY(0)', opacity: '1' } },
        slideDown: { '0%': { transform: 'translateY(-10px)', opacity: '0' }, '100%': { transform: 'translateY(0)', opacity: '1' } },
        glow: { '0%': { boxShadow: '0 0 5px rgba(0,212,170,0.2)' }, '100%': { boxShadow: '0 0 20px rgba(0,212,170,0.27)' } },
      }
    },
  },
  plugins: [],
}
