# Market Scanner Pro — Project Documentation

> Onboarding snapshot: 21 June 2026. This document describes the code present in the workspace; it does not assume that the README's setup claims are current.

## 1. System overview

Market Scanner Pro is a two-process, full-stack market-research application:

| Layer | Implementation | Responsibility |
|---|---|---|
| Browser client | React 18 SPA built by Vite 6 | Scanner UI, results, market-detail modal/chart, news, fundamentals, watchlist, authentication modal, and admin UI |
| API server | Flask 3 monolith in `backend/app.py` | REST API, SQLite persistence, Polygon data access, technical analysis, news aggregation, sentiment, fundamentals, and authorization |
| Persistence | SQLite locally; SQLAlchemy | Users, watchlists, scan results, and scan history |
| Market-data providers | Polygon.io primarily; optional Finnhub, Alpha Vantage, RSS feeds | OHLCV data, ticker metadata, news, financial statements, dividends |

The frontend has no client-side router. `App.jsx` switches between five in-memory pages (`scanner`, `newsroom`, `fundamentals`, `watchlist`, and conditional `admin`). In development, Vite proxies `/api` to Flask at `127.0.0.1:5000`.

### Runtime flow

```text
React/Vite :5173
  ├─ /api/* proxy ───────────────────────────────► Flask :5000
  ├─ Zustand stores ◄──────── JSON ────────────────┤
  └─ Lightweight Charts renders Polygon OHLCV data  ├─ Polygon.io
                                                    ├─ SQLite / SQLAlchemy
                                                    ├─ Finnhub / Alpha Vantage (optional)
                                                    └─ RSS feeds (optional `feedparser` dependency)
```

## 2. Repository layout and generated artifacts

```text
.
├── README.md
├── .venv/                         # local virtual environment; generated
├── backend/
│   ├── .env                        # present locally; contains secrets/configuration
│   ├── app.py                      # active Flask application (2,641 lines)
│   ├── requirements.txt
│   ├── instance/market_scanner.db  # SQLite runtime database
│   ├── routes/scan.py              # orphaned, incompatible scan blueprint
│   ├── services/scanner.py          # orphaned, incompatible scanner service
│   └── venv/                       # checked-in/generated virtual environment
└── frontend/
    ├── index.html
    ├── package.json / package-lock.json
    ├── vite.config.js / tailwind.config.js / postcss.config.js
    ├── public/favicon.svg
    ├── node_modules/               # installed dependency tree; generated
    └── src/
        ├── App.jsx / main.jsx / index.css
        ├── components/
        ├── constants/timeframes.js
        ├── services/api.js
        └── store/
```

`backend/venv`, `.venv`, `frontend/node_modules`, the SQLite database, and a Vite build output are generated/runtime artifacts and are not application source. The backend virtual environment is not portable: its `pyvenv.cfg` references the missing interpreter under `C:\Users\abasa\...`, so `backend\venv\Scripts\python.exe` cannot run in this workspace. The root `.venv` points to the current user's Python installation.

There is no project-local `.git` directory or `.gitignore`. The enclosing Git worktree resolves to `C:\` and cannot be fully enumerated under the current permissions, so this review cannot prove whether the secret `.env`, database, or environments have been committed. They should be treated as at risk until the repository boundary is fixed and verified.

## 3. Dependencies, scripts, and build configuration

### Frontend package

Package manager: npm; lockfile format: npm lockfile v3. The `package.json` script surface is deliberately small:

| Script | Command | Purpose |
|---|---|---|
| `dev` | `vite` | Local development server |
| `build` | `vite build` | Production bundle |
| `preview` | `vite preview` | Serve a production bundle locally |

Direct dependency declarations and currently locked resolutions are below. A caret range in `package.json` permits the newer locked version.

| Package | Declared | Locked/installed | Role |
|---|---:|---:|---|
| `react`, `react-dom` | `^18.3.1` | `18.3.1` | UI runtime |
| `zustand` | `^5.0.2` | `5.0.11` | Global client stores |
| `axios` | `^1.7.9` | `1.13.5` | HTTP client |
| `lightweight-charts` | `^4.2.1` | `4.2.3` | Candlestick chart rendering |
| `lucide-react` | `^0.468.0` | `0.468.0` | Icons |
| `react-hot-toast` | `^2.4.1` | `2.6.0` | Notifications |
| `vite` | `^6.0.5` | `6.4.1` | Build/dev server |
| `@vitejs/plugin-react` | `^4.3.4` | `4.7.0` | React transform |
| `tailwindcss` | `^3.4.17` | `3.4.19` | Utility CSS |
| `postcss`, `autoprefixer` | `^8.4.49`, `^10.4.20` | `8.5.6`, `10.4.27` | CSS pipeline |
| `@types/react`, `@types/react-dom` | `^18.3.x` | `18.3.28`, `18.3.7` | Editor types only; source is JavaScript |

### Backend package

`backend/requirements.txt` pins Flask 3.1.0, Flask-CORS 5.0.0, Flask-SQLAlchemy 3.1.1, SQLAlchemy 2.0.36, pandas 2.2.3, NumPy 2.1.3, requests 2.32.3, python-dotenv 1.0.1, Werkzeug 3.1.3, and gunicorn 23.0.0. There is no Python lockfile, dependency hash file, or production process configuration.

Two optional runtime capabilities are not in `requirements.txt`:

- `transformers` and `torch` enable FinBERT. Without them, sentiment falls back to a local word-list scorer.
- `feedparser` enables Google News, Yahoo Finance, and MarketWatch RSS. Without it, those sources silently return no articles (with a log warning for Google only).

### Configuration files

| File | Observed behavior |
|---|---|
| `frontend/vite.config.js` | React plugin; host exposed on the network; port `5173`; `/api` proxy to `127.0.0.1:5000` with ten-minute proxy timeouts; production output `dist`; sourcemaps disabled. |
| `frontend/tailwind.config.js` | Scans `index.html` and `src`; maps scanner design tokens to CSS variables; defines fonts, shadows, and animations. |
| `frontend/postcss.config.js` | Runs Tailwind and Autoprefixer. |
| `frontend/index.html` | Static root element, SEO description, favicon, and Google-hosted DM Sans, JetBrains Mono, and Outfit fonts. |
| `frontend/src/index.css` | Dark default/light theme variables, base styling, scrollbar, glass, skeleton, and theme-transition helpers. |
| `backend/.env` | Local secret/config file exists. Values were intentionally not copied into this documentation. |

No `.env.example`, ESLint/Prettier configuration, TypeScript configuration, Jest/Vitest configuration, Dockerfile, Compose file, GitHub Actions workflow, or test configuration exists.

## 4. Environment and configuration

| Variable | Used by | Required? | Meaning / fallback |
|---|---|---|---|
| `POLYGON_API_KEY` | `PolygonClient` | Yes for useful data | Polygon API key. Empty by default; health reports whether it is configured. |
| `DATABASE_URL` | Flask-SQLAlchemy | No locally; yes for production design | Defaults to `sqlite:///market_scanner.db`, resolving to Flask's instance database. README claims PostgreSQL is suitable for production, but no PostgreSQL deployment or migrations are supplied. |
| `SECRET_KEY` | Flask | Required in production | Falls back to a random value at each process start, invalidating Flask-signed state across restarts. |
| `FINNHUB_API_KEY` | `NewsAggregator` | Optional | Enables Finnhub company news. It is read by code but absent from the observed `.env` key list. |
| `ALPHA_VANTAGE_KEY` | `NewsAggregator` | Optional | Enables Alpha Vantage news sentiment. It is read by code but absent from the observed `.env` key list. |
| `VITE_API_URL` | `frontend/src/services/api.js` | Optional | Prefix before `/api`; defaults to same-origin so Vite's proxy works in development. |
| `FLASK_ENV` | `.env` only | Ambiguous | Present locally but not read by application code. Flask is explicitly started with `debug=True` when `app.py` is run. |

Recommended local startup is `python app.py` from `backend` and `npm run dev` from `frontend`, after recreating the backend virtual environment. The README's default administrative password must not be used outside an isolated development database.

## 5. Entry points and navigation

| Entry point | Responsibilities |
|---|---|
| `frontend/src/main.jsx` | Imports global styles and mounts `<App />` under React Strict Mode. |
| `frontend/src/App.jsx` | Initializes theme/auth/health/filter data, checks API health every minute, owns the page selector, mounts common UI/modals, and renders the selected page. |
| `backend/app.py` | Creates Flask/SQLAlchemy, loads environment values, constructs long-lived service objects, declares every active API route, runs `db.create_all()`, and creates a default admin when none exists. |

Client navigation is state only, not URLs. Refreshing the page always returns to the scanner. The app has no `/login` route despite the Axios error interceptor assigning `window.location.href = '/login'` on a 401.

## 6. Active REST API

All active routes are defined in `backend/app.py`. Flask-CORS permits all origins for `/api/*`.

| Method | Path | Auth | Inputs | Response / behavior |
|---|---|---|---|---|
| GET | `/api/health` | Public | — | Status, Polygon configuration boolean, universe sizes, UTC timestamp. |
| POST | `/api/auth/register` | Public | `username`, `email`, `password` | Creates user, returns user and in-memory bearer token. Password minimum is six characters. |
| POST | `/api/auth/login` | Public | `email` (also accepts username), `password` | Validates active user and returns user/token. |
| GET | `/api/auth/me` | Bearer token | — | Current user. |
| POST | `/api/auth/change-password` | Bearer token | `current_password`, `new_password` | Changes hash. Does not validate a missing body or new-password strength. |
| GET | `/api/filters` | Public | — | Filter definitions, presets, and an availability description for selected timeframes. |
| GET | `/api/search` | Public | `q`, `market` | Polygon ticker-reference search, capped to 15 returned items. |
| GET | `/api/stock/<symbol>` | Public | `timeframe` | OHLCV-derived technical analysis, ticker metadata, trade setup, and chart bars. Rejects listed intraday keys. |
| GET | `/api/chart/<symbol>` | Public | `timeframe` | Raw OHLCV bars. Unlike stock/scan it does not reject intraday keys. Not used by the current frontend. |
| POST | `/api/scan` | Public | `market`, `filters[]`, `timeframe`, `limit` | Sequentially scans the fixed universe; a result is included if **any** selected filter matches; persists matches/history. |
| GET | `/api/watchlist` | Bearer token | — | Current user's watchlist. |
| POST | `/api/watchlist` | Bearer token | `symbol`, optional `market`, `notes` | Adds a symbol, rejecting duplicate symbol per user (market is not part of the uniqueness check). |
| DELETE | `/api/watchlist/<id>` | Bearer token | — | Deletes an item belonging to the current user. |
| GET | `/api/admin/users` | Admin bearer token | — | All users. |
| PUT | `/api/admin/users/<id>` | Admin bearer token | `role`, `plan`, `is_active` | Updates supplied fields without allow-list validation. |
| GET | `/api/admin/scans` | Admin bearer token | — | Latest 50 scan-history rows. |
| GET | `/api/admin/stats` | Admin bearer token | — | User/scan counts and in-memory cache size. |
| GET | `/api/news/<symbol>` | Public | `limit`, `sentiment`, `source`, `days` | Multi-source articles, sentiment, sources, active feeds, and filtered total. |
| GET | `/api/fundamentals/<symbol>` | Public | — | Polygon-derived company overview, valuation, profitability, growth, health, dividend data, and generated prose summary. |

### API client contract

`frontend/src/services/api.js` centralizes Axios calls with a default 30-second timeout and longer timeouts for scan/detail/fundamentals/news. It exports grouped API objects for auth, market, news, fundamentals, watchlist, admin, and health.

Important current contract defects:

- Auth store persists `auth_token`, while Axios reads and clears `access_token` (and a nonexistent `refresh_token`). Consequently, the bearer header is not sent after login/register and protected watchlist/admin operations fail.
- `AdminPanel` calls `adminAPI.getScanHistory()`, but the client exposes `adminAPI.getScans()`. Its `Promise.all` rejects, so the whole admin panel remains unloaded.
- The client exposes `adminAPI.deleteUser`, but Flask defines no matching DELETE route.

## 7. Backend modules and behavior

### `backend/app.py`

This single module is both application composition root and domain implementation.

| Area | Key inputs/outputs | Dependencies and notable logic |
|---|---|---|
| App setup | Environment → Flask config/`db` | `load_dotenv`, global wildcard CORS, SQLAlchemy. |
| Models | SQLAlchemy models → database rows/JSON | Defines `User`, `Watchlist`, `ScanResult`, `ScanHistory`; only `User` has `to_dict`. |
| Auth helpers | Bearer header → `g.user_id` | `generate_token` stores random tokens in global `_tokens`; `token_required` expires at 24h; `admin_required` checks `role == 'admin'`. Tokens are process-local and nonpersistent. |
| Cache helpers | String key/data → `_cache` | Process-local dictionary. `cache_set` stores a custom TTL but `cache_get` always uses global five-minute TTL, so supplied 10-minute/one-hour TTLs are ignored. |
| `PolygonClient` | Polygon endpoints → Python JSON/list | Shared `requests.Session`, process-local 12.5-second rate limiting, 30-second request timeout, retry-by-recursion after a 429. Supports aggregates, snapshots, reference search/details, prior close, news, financials, and dividends. |
| `SentimentAnalyzer` | Article text → `{label, score, method}` | Attempts FinBERT once at import; falls back to a simple unique-word lexicon. No model packages are in requirements. |
| `TechnicalAnalysis` | OHLCV bars → `analysis` JSON | Calculates SMA/EMA, RSI, MACD, Bollinger bands, stochastic, ATR, Fibonacci levels/zones, candle/chart patterns, signal counts, and an ATR/fib/support-resistance trade setup. |
| Symbol/timeframe configuration | User market/timeframe → Polygon aggregate parameters | Fixed 80-stock and 15-crypto universes. Daily/week/month/year are supported; defined intraday entries are rejected by detail/scan as paid-plan-only. |
| Filters/presets | Analysis → boolean matches | Five categories: oscillators, moving averages, volatility, patterns, Fibonacci. The scan returns partial matches and ranks by match percentage; it does not require all filters in a preset. |
| News aggregation | Symbol + options → normalized articles | Merges Polygon, optional Finnhub/Alpha Vantage, and optional RSS sources; first-60-character title dedupe; filters/sorts by date; caches article set. |
| Fundamentals | Polygon details/financials/dividends → dashboard DTO | Safely extracts Polygon's nested values, derives metrics and a heuristic plain-English summary, then requests a one-hour cache (currently only five minutes in practice). |
| Initialization | App context → schema/default admin | Calls `db.create_all()` rather than migrations; if no admin exists, creates `admin@marketscanner.local` with password `admin123`; starts the Werkzeug debugger with `debug=True` when executed directly. |

### Technical-analysis output shape

`TechnicalAnalysis.full_analysis(bars)` requires at least 30 bars. It returns:

```json
{
  "price": {"last": 0, "change_pct": 0, "open": 0, "high": 0, "low": 0, "volume": 0},
  "indicators": {"rsi": 0, "macd": {}, "ema": {}, "sma": {}, "bollinger_bands": {}, "stochastic": {}},
  "fibonacci": {"trend": "uptrend", "zones": [], "supports": [], "resistances": []},
  "patterns": {"candlestick": [], "chart": []},
  "signals": [],
  "overall_signal": "bullish|bearish|neutral",
  "signal_counts": {"bullish": 0, "bearish": 0},
  "trade_setup": {}
}
```

The algorithm is heuristic rather than an investment recommendation or a backtested model. Several indicators return `None` for insufficient history; UI code generally handles this with placeholders.

### Orphaned backend files

| File | Status | Why it is not part of the running app |
|---|---|---|
| `backend/routes/scan.py` | Inactive and broken if imported | Declares a JWT-protected `/api/scan/run` blueprint but imports unavailable `flask_jwt_extended`, `models`, `models.user`, and an incompatible service. `app.py` neither imports nor registers it. |
| `backend/services/scanner.py` | Inactive and broken if imported | Imports missing `services.polygon_api`, `services.technical_analysis`, and `config`; expects model fields that do not exist in the active `ScanResult`. It represents a prior architecture, not a usable second scanner. |

Python AST parsing succeeded for all three backend Python source files. This confirms syntax only, not imports or runtime behavior.

## 8. Data layer

SQLite database path: `backend/instance/market_scanner.db` (69,632 bytes at review). Existing data counts were 1 user, 0 watchlists, 165 scan results, and 6 scan-history rows; values and password hashes were not inspected.

| Model/table | Columns | Relations / observations |
|---|---|---|
| `users` / `User` | `id`, unique/indexed `username`, unique/indexed `email`, `password_hash`, `role`, `plan`, `created_at`, `is_active` | One-to-many `watchlists`, cascade delete-orphan. No migration history or check constraints. |
| `watchlists` / `Watchlist` | `id`, `user_id`, `symbol`, `market`, `added_at`, `notes` | FK to `users`; no database uniqueness constraint for `(user_id, symbol)`, despite API-level duplicate check. |
| `scan_results` / `ScanResult` | `id`, `symbol`, `market`, `scan_type`, `scan_date`, `filters_matched`, `indicator_values`, `last_price`, `volume`, `signal` | Stores JSON as text. No foreign key to user or scan-history record. Indexed by symbol and date. |
| `scan_history` / `ScanHistory` | `id`, `scan_date`, `market`, `total_scanned`, `total_matched`, `filters_used`, `duration_seconds` | Global operational history; filters stored as JSON text and no user ownership. |

Schema is created opportunistically with `db.create_all()` at application import. There are no migrations, seed scripts, retention jobs, backups, or indexes on `watchlists.user_id` / `scan_history.scan_date`.

## 9. Frontend modules

### Stores and shared services

| File | Purpose, inputs, and dependencies |
|---|---|
| `src/services/api.js` | Axios instance and grouped calls. Reads `VITE_API_URL`; adds an incorrectly keyed auth interceptor; calls all active backend endpoints except `/chart`. |
| `src/store/useAuthStore.js` | Zustand auth state. Loads/stores user and `auth_token` in localStorage; performs login/register/me/logout; controls `AuthModal`. |
| `src/store/useMarketStore.js` | Market selector, filters/presets/timeframe, scan lifecycle, detail modal/chart data, search, watchlist, and API health. Uses market/watchlist APIs. |
| `src/store/useNewsStore.js` | Symbol/news payload and server-side sentiment/source/date filters. Refetches on filter change and uses toasts on failure. |
| `src/store/useFundamentalsStore.js` | Fundamental dashboard data, current symbol, loading/error, API fetch, reset/toast. |
| `src/store/useThemeStore.js` | Persists dark/light setting in localStorage and sets `data-theme` on `<html>`. |
| `src/constants/timeframes.js` | Exports minute, hour+, combined timeframe arrays, default `1D`, and a set of paid-plan intraday keys. |

### Components

| File | Purpose and important dependencies |
|---|---|
| `src/components/common/Header.jsx` | Logo, market toggle, page navigation, theme, responsive menu, profile/logout. Admin navigation is rendered only from client `user.role`. |
| `src/components/common/SearchBar.jsx` | Debounced (300 ms) ticker search/dropdown; opens the market-detail modal. |
| `src/components/common/ThemeToggle.jsx` | Dark/light mode control using `useThemeStore`. |
| `src/components/common/LoadingSpinner.jsx` | Spinner plus reusable skeleton row/card. |
| `src/components/filters/FilterPanel.jsx` | Filter category accordions, all configured timeframes, presets, and scan trigger. It exposes paid intraday buttons even though backend rejects them. |
| `src/components/stock/ScanResults.jsx` | Empty/loading/error/table states, expandable trade setup, detail and authenticated watchlist actions. |
| `src/components/stock/StockDetailModal.jsx` | Detail modal with chart, timeframes, indicators, patterns, Fibonacci levels/zones, signals, and watchlist action. It strips `X:` from selected crypto symbols, breaking later timeframe changes and watchlist detail requests. |
| `src/components/stock/WatchlistPage.jsx` | Auth-gated watchlist loading, detail and delete actions. Notes are not displayed/edited. |
| `src/components/charts/CandlestickChart.jsx` | Memoized Lightweight Charts instance: candle/volume data plus client-computed EMA and Bollinger overlays. Recreates chart when `data`, `height`, or `indicators` object changes. |
| `src/components/TradeSetupCard.jsx` | Compact/expanded display of API-supplied trade setup, targets, risk/reward, levels, Fibonacci position, and disclaimer. |
| `src/components/auth/AuthModal.jsx` | Login/register form with simple client validation and store actions. No password-change, reset, or recovery UI. |
| `src/components/admin/AdminPanel.jsx` | Client-side role guard; overview/users/scans tables. Fails while loading due to calling nonexistent `adminAPI.getScanHistory`. |
| `src/components/news/NewsRoom.jsx` | Symbol search, aggregate sentiment summary, source/date/sentiment filtering, responsive external article cards. |
| `src/components/fundamentals/FundamentalAnalysis.jsx` | US-stock search and cards/bars for all fundamental API sections. |

### UI and data-flow notes

- `CandlestickChart` recomputes visual EMAs/Bollinger bands from raw candles; values can differ slightly from backend calculations because the standard-deviation formulas differ.
- `SearchBar` correctly passes Polygon's crypto `X:` ticker to the initial detail request. `useMarketStore.openDetail` then stores a stripped symbol; `changeDetailTimeframe` subsequently requests the stripped value and fails for crypto. A watchlist scan result stores/display strips the prefix too, so crypto watchlist detail has the same issue.
- The scan loading bar has a fixed 60% width. The backend is synchronous and provides no progress endpoint or event stream.
- `get_filters` advertises `4H` as unavailable, but neither `TIMEFRAME_MAP` nor the frontend includes a `4H` key. This is an API metadata inconsistency.

## 10. Authentication and authorization

The backend uses opaque, random bearer tokens, not JWTs. Tokens are a Python dictionary mapping token to user id/creation time; they expire after 24 hours and disappear on restart or on a different worker. Passwords use Werkzeug hashing. `User.role` controls admin API access; `plan` is display/management data only.

Protected resources are watchlist routes and `/api/auth/me`/change-password; admin routes additionally require `role == 'admin'`. The scanner, market data, news, and fundamentals are intentionally public.

The frontend's intended persistence design is localStorage. Because its storage key does not match the API interceptor key, authorization currently fails after login. There is no refresh-token endpoint despite the interceptor referring to one, no logout/revocation API, no authentication rate limiting, no email verification/recovery, and no CSRF model (the app currently uses bearer tokens rather than cookies).

## 11. Third-party integrations

| Integration | Call site | Function |
|---|---|---|
| Polygon.io | `PolygonClient`, fundamentally all market endpoints | OHLCV aggregate bars, ticker search/details, prior close, news, financial statements, dividends. Shared 12.5-second in-process spacing and a five-minute effective cache are intended to protect quota. |
| Finnhub | `NewsAggregator._fetch_finnhub` | Optional company news for stock symbols. |
| Alpha Vantage | `NewsAggregator._fetch_alpha_vantage` | Optional news/sentiment feed. |
| Google News RSS | `NewsAggregator._fetch_google_rss` | Optional feedparser-based symbol/company searches. |
| Yahoo Finance RSS | `NewsAggregator._fetch_yahoo_rss` | Optional feedparser-based headlines. |
| MarketWatch RSS | `NewsAggregator._fetch_marketwatch_rss` | Optional broad feed filtered by symbol mentioned in title. |
| FinBERT | `SentimentAnalyzer` | Optional local ML classifier; otherwise no external model call. |
| Google Fonts | `frontend/index.html` | Hosted visual fonts. |
| Lightweight Charts | `CandlestickChart.jsx` | Browser-only market chart visualization. |

Provider terms, entitlement, and current rate limits should be confirmed directly with each provider before production release. The README's Polygon free-tier claims are not enforced or verified in code.

## 12. Tests, quality gates, and validation

No repository-owned unit, integration, API, component, or end-to-end tests were found. There is no lint, format, typecheck, pre-commit, CI, container, or deployment configuration.

Read-only/reversible validation performed during this review:

| Check | Result |
|---|---|
| Python AST parse of `app.py`, orphaned route, and orphaned scanner | Passed; this does not execute imports or test behavior. |
| `npm run build` to a temporary directory | Passed with Vite 6.4.1: 1,659 modules; JS 490.30 kB (147.59 kB gzip), CSS 27.30 kB (6.14 kB gzip). The bundle is large enough for code splitting to be worthwhile. |
| `npm audit --package-lock-only --json` | 25 findings: 4 high, 17 moderate, 4 low, 0 critical. See improvement plan for immediate remediation. |

## 13. Explicit TODO/FIXME/HACK/deprecation search

Searching application-owned source/configuration (`README.md`, active backend source, orphaned backend source, `frontend/src`, and frontend configuration/public files) found **no explicit** `TODO`, `FIXME`, `HACK`, `BUG`, or `@deprecated` comments. Third-party virtual-environment and `node_modules` files contain their own markers and are excluded from this result.

## 14. Ambiguities and questions to resolve

1. Is this directory intended to become its own Git repository? Its current parent Git root is `C:\`, which prevents normal project-level source-control checks and likely explains the absence of a project-local ignore file.
2. Is `backend/routes/scan.py` / `backend/services/scanner.py` a discarded prototype or a migration in progress? It cannot coexist with the active monolith without a deliberate reconciliation.
3. Which Polygon plan/data entitlements are actually available in deployment? The UI advertises certain paid intraday capabilities but does not disable actions, and the provider's product rules may differ from the README.
4. Are RSS aggregation and FinBERT intended production features? Their required packages are not declared, so the current deployed behavior is the lexicon fallback and no RSS articles unless environment drift supplies dependencies.
5. Should scans be public, user-owned, or premium-plan-gated? Today all callers can initiate expensive provider-backed scans, while resulting history is global and has no user id.

