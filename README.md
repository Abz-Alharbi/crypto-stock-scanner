# Market Scanner Pro

Advanced stock & cryptocurrency technical analysis scanner with interactive charts, pattern detection, and real-time market scanning.

## Features

- **Multi-Market Support**: US stocks (NYSE + NASDAQ, 80 symbols) and major cryptocurrencies (15 symbols)
- **Technical Indicators**: RSI, MACD, EMA (9/20/50/200), SMA (20/50/200), Bollinger Bands, Stochastic Oscillator, Fibonacci Retracements
- **Pattern Detection**: Japanese candlestick patterns (Doji, Hammer, Engulfing, Morning/Evening Star, Shooting Star) + chart patterns (Double Top/Bottom, Triangles, Flags)
- **Interactive Charts**: TradingView-powered candlestick charts with volume, EMA overlays, and Bollinger Bands
- **Scanning Engine**: Filter-based market scanning with preset strategies (Bullish Momentum, Oversold Bounce, Trend Following, Bearish Reversal)
- **Multiple Timeframes**: 1H, 4H, 1D, 1W, 1M
- **User Authentication**: Registration, login, password management
- **Watchlist**: Save and track favorite assets
- **Admin Panel**: User management, scan history, system stats
- **Mobile Responsive**: Works on desktop, tablet, and phone

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + Vite, TailwindCSS, Zustand, Lightweight Charts |
| Backend | Python Flask, SQLAlchemy, Pandas, NumPy |
| Database | SQLite (local) / PostgreSQL (production) |
| Data API | Polygon.io (free tier: 5 calls/min) |

---

## Setup Instructions (VS Code / Localhost)

### Prerequisites

- **Python 3.10+** — [Download](https://python.org)
- **Node.js 18+** — [Download](https://nodejs.org)
- **Polygon.io API Key** — [Get free key](https://polygon.io) (already configured in `.env`)

---

### Step 1: Backend Setup

Open a terminal in VS Code:

```bash
# Navigate to backend folder
cd backend

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the backend server
python app.py
```

You should see:
```
============================================================
  Market Scanner Pro - Backend API
  Polygon API Key: ✓ Configured
  Stock symbols: 80
  Crypto symbols: 15
  Rate limit: 12.5s between API calls
============================================================
 * Running on http://127.0.0.1:5000
```

**Test it**: Open `http://localhost:5000/api/health` in your browser.

---

### Step 2: Frontend Setup

Open a **second terminal** in VS Code:

```bash
# Navigate to frontend folder
cd frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

You should see:
```
  VITE v6.x.x  ready in XXX ms

  ➜  Local:   http://localhost:5173/
```

**Open**: `http://localhost:5173` in your browser.

---

### Step 3: Use the App

1. **Select Market**: Toggle between Stocks and Crypto in the header
2. **Choose Filters**: Pick indicators from the left panel (RSI Oversold, MACD Bullish, etc.)
3. **Or Use Presets**: Click a quick preset like "Bullish Momentum" or "Oversold Bounce"
4. **Select Timeframe**: Choose from 1H, 4H, 1D, 1W, 1M
5. **Run Scan**: Click the green "Run Scan" button
6. **Wait**: Scanning takes a few minutes on free tier (5 API calls/min rate limit)
7. **View Results**: Click any result row to see detailed analysis with charts, indicators, patterns, and Fibonacci levels
8. **Search**: Type a ticker (e.g., AAPL, NVDA) in the search bar for direct analysis

---

## Default Admin Account

```
Email:    admin@marketscanner.local
Password: admin123
```

Use this to access the Admin Panel (manage users, view scan history, system stats).

**⚠️ Change this password in production!**

---

## API Rate Limiting

The free Polygon.io tier allows **5 API calls per minute**. The backend automatically handles this with:
- 12.5-second delay between API calls
- In-memory caching (5-minute TTL)
- Efficient batch processing

**Scan times** (approximate):
| Stocks | Time |
|--------|------|
| 20 stocks | ~4 minutes |
| 50 stocks | ~10 minutes |
| 80 stocks | ~17 minutes |

---

## Project Structure

```
market-scanner-pro/
├── backend/
│   ├── app.py              # Flask API (all routes, analysis engine, models)
│   ├── requirements.txt    # Python dependencies
│   └── .env                # API key + config (DO NOT commit to git)
│
├── frontend/
│   ├── public/
│   │   └── favicon.svg
│   ├── src/
│   │   ├── components/
│   │   │   ├── admin/
│   │   │   │   └── AdminPanel.jsx
│   │   │   ├── auth/
│   │   │   │   └── AuthModal.jsx
│   │   │   ├── charts/
│   │   │   │   └── CandlestickChart.jsx
│   │   │   ├── common/
│   │   │   │   ├── Header.jsx
│   │   │   │   ├── LoadingSpinner.jsx
│   │   │   │   └── SearchBar.jsx
│   │   │   ├── filters/
│   │   │   │   └── FilterPanel.jsx
│   │   │   └── stock/
│   │   │       ├── ScanResults.jsx
│   │   │       ├── StockDetailModal.jsx
│   │   │       └── WatchlistPage.jsx
│   │   ├── constants/
│   │   │   └── timeframes.js
│   │   ├── services/
│   │   │   └── api.js
│   │   ├── store/
│   │   │   ├── useAuthStore.js
│   │   │   └── useMarketStore.js
│   │   ├── App.jsx
│   │   ├── index.css
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   ├── postcss.config.js
│   ├── tailwind.config.js
│   └── vite.config.js
│
└── README.md
```

---

## API Endpoints

### Public
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | System health check |
| GET | `/api/filters` | Get all filter definitions & presets |
| GET | `/api/search?q=AAPL&market=stocks` | Search tickers |
| GET | `/api/stock/<symbol>?timeframe=1D` | Detailed stock analysis |
| GET | `/api/chart/<symbol>?timeframe=1D` | OHLCV chart data |
| POST | `/api/scan` | Run market scan with filters |

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Sign in |
| GET | `/api/auth/me` | Get current user |
| POST | `/api/auth/change-password` | Change password |

### Protected (requires auth)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/watchlist` | Get user watchlist |
| POST | `/api/watchlist` | Add to watchlist |
| DELETE | `/api/watchlist/<id>` | Remove from watchlist |

### Admin (requires admin role)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/users` | List all users |
| PUT | `/api/admin/users/<id>` | Update user role/plan |
| GET | `/api/admin/scans` | Scan history |
| GET | `/api/admin/stats` | System statistics |

---

## Legal Disclaimer

⚠️ **This application is for educational and informational purposes only.** It does not constitute financial, investment, or trading advice. Technical analysis indicators and patterns are not guarantees of future performance. Always conduct your own research and consult with a licensed financial advisor before making investment decisions. Past performance does not indicate future results.

---

## License

MIT
