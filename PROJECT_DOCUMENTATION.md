# Market Scanner Pro - Project Documentation

Last regenerated: 2026-07-13

This document was regenerated from the current codebase. It intentionally does not treat the previous `PROJECT_DOCUMENTATION.md` as a source of truth.

## Architecture Overview

Market Scanner Pro is a React/Vite frontend backed by a Flask API. The backend now uses a factory pattern instead of a monolithic app module:

- `backend/app.py` is the entry point and exposes `app = create_app()`.
- `backend/factory.py` builds the Flask app, loads config, initializes extensions, registers blueprints, installs error handlers, applies security headers, loads the YOLO service, and registers CLI commands.
- `backend/config.py` defines `DevelopmentConfig`, `ProductionConfig`, and `TestingConfig`.
- `backend/extensions.py` owns shared Flask extensions: SQLAlchemy and Flask-Migrate.

The runtime architecture is:

- Flask API served by Gunicorn in production.
- PostgreSQL in Railway production through `DATABASE_URL`.
- Redis for auth tokens, token revocation, API cache, rate-limit counters, scan job state, and RQ queue storage.
- RQ worker for background scans, scan-template sweeps, and universe rebuild jobs.
- React/Vite frontend deployed separately and configured with `VITE_API_URL`.
- Polygon/Massive market data provider through `backend/clients/polygon.py`.

Security defaults:

- `DEBUG=False` unless `FLASK_ENV=development`.
- CORS origins come from `ALLOWED_ORIGINS`, defaulting to `http://localhost:5173`.
- Every backend response gets:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Strict-Transport-Security: max-age=63072000`

## Backend Structure

Current backend layout:

| Path | Purpose |
|---|---|
| `backend/app.py` | Entry point only. Imports and calls `create_app()`. |
| `backend/factory.py` | Flask app factory, blueprint registration, CLI commands, headers, YOLO startup, optional schedulers. |
| `backend/config.py` | Environment-backed config classes and config selection. |
| `backend/extensions.py` | Shared `db` and `migrate` extension instances. |
| `backend/errors.py` | `ApiError` plus JSON error handlers for validation, 404, 405, and 500. |
| `backend/logging_config.py` | JSON logging using `python-json-logger`, with fallback formatter. |
| `backend/market_config.py` | Canonical timeframe map and `/api/filters` timeframe payload helper. |
| `backend/symbols.py` | Canonical symbol handling: `{ provider_symbol, display_symbol, market }`. |
| `backend/models/` | SQLAlchemy models. |
| `backend/auth/` | Auth routes, service, and auth request schemas. |
| `backend/api/` | Thin route modules. Most routes validate, call a service, then return JSON. |
| `backend/schemas/` | Pydantic request/query schemas and parse helpers. |
| `backend/clients/polygon.py` | Polygon/Massive transport only. Timeout, retries, concurrency, cache, circuit breaker. |
| `backend/domain/` | Typed asset-class, instrument, timeframe, and market-data request values. |
| `backend/providers/` | Provider-neutral market-data protocol and Polygon adapter. |
| `backend/strategies/` | Strategy contract, built-in registry, 22 legacy filter adapters, capability configuration, and RSI demo strategy. |
| `backend/strategy_runtime.py` | Compatibility and orchestration facade over the strategy registry. |
| `backend/services/` | Business logic for scans, indicators, cache, Redis, patterns, news, fundamentals, watchlist, templates, notifications, universe. |
| `backend/jobs/` | RQ job bodies for scans, template sweeps, and universe rebuilds. |

Current backend blueprints:

| Blueprint | Prefix | Notable endpoints |
|---|---|---|
| Auth | `/api/auth` | Register, login, me, change password, logout. |
| Scanner | `/api` | Health, filters, universe status, search, stock detail, chart data, async scan, scan status, cancel, SSE stream, scan templates. |
| Watchlist | `/api/watchlist` | List, add, remove, update notes. |
| News | `/api/news` | News by symbol. Backend route is public; frontend route is auth-guarded. |
| Fundamentals | `/api/fundamentals` | Fundamentals by symbol. Backend route is public; frontend route is auth-guarded. |
| Admin | `/api/admin` | Users, user update, scan history, stats, audit logs. Requires admin token. |
| Patterns | `/api/patterns/detect` | Auth-required YOLOv8 pattern detection from a client-captured chart image. |
| Ops | none | `/health`, `/ready`. |
| Notifications | `/api/notifications` | List notifications and mark read. Requires token. |

## Async Scan Job Flow

Bulk scans are asynchronous:

1. Frontend posts to `POST /api/scan` with `{ market, timeframe, filters, limit }`.
2. `backend/api/scan_routes.py` validates with `ScanRequest`.
3. `backend/services/scan_jobs.py` creates a UUID job id and writes queued state to Redis.
4. Unless `SCAN_QUEUE_SYNC=true`, the request enqueues `worker.run_scan_job` into the RQ queue.
5. `worker.py` delegates to `backend.jobs.scan_jobs.run_scan_job`.
6. The job creates an app context, runs `backend.services.scans.scan_market`, and writes progress to Redis.
7. Frontend polls `GET /api/scan/status/<job_id>`.
8. `DELETE /api/scan/<job_id>` marks a Redis cancel key and cancels the RQ job where possible.
9. `GET /api/scan/stream/<job_id>` streams status through server-sent events.
10. Completed matches are stored in `scan_results`; each scan writes a `scan_history` row.

Redis keys used by scans include:

- `scan_job:{job_id}:state`
- `scan_job:{job_id}:cancel`
- RQ queue data under Redis-managed RQ keys.

## Data Provider: Massive/Polygon Integration

The code calls the provider through `backend/clients/polygon.py`. The class is named `PolygonClient`; documentation and deploy notes sometimes refer to Massive/Polygon because the provider branding changed.

Provider endpoints used:

| Endpoint | Used for |
|---|---|
| `/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}` | Chart data, stock detail, scan OHLCV bars. |
| `/v2/aggs/grouped/locale/us/market/stocks/{date}` | Universe builder volume history. One call returns all US stock OHLCV for that day. |
| `/v3/reference/tickers?market=stocks&type=CS&exchange=...` | Universe builder eligible common-stock ticker sets. Fully paginated through `next_url`. |
| `/v3/reference/tickers` | Symbol search. |
| `/v3/reference/tickers/{ticker}` | Stock details, company name lookup for news/fundamentals. |
| `/v2/snapshot/locale/us/markets/stocks/tickers` | Optional stock snapshot prefilter when `POLYGON_SNAPSHOT_PREFILTER=true`. |
| `/v2/snapshot/locale/global/markets/crypto/tickers` | Optional crypto snapshot prefilter. |
| `/v2/aggs/ticker/{ticker}/prev` | Previous close used by fundamentals. |
| `/v2/reference/news` | Polygon news source. |
| `/vX/reference/financials` | Fundamentals. |
| `/v3/reference/dividends` | Dividend data. |

Transport behavior:

- Per-request timeout is 10 seconds.
- Network timeouts/connection failures and HTTP 429 responses retry iteratively with exponential backoff and jitter, max 3 retries; 429 honors `Retry-After`.
- HTTP 5xx responses record a circuit-breaker failure but return without retry, and other `RequestException` failures also return after the first attempt.
- Circuit breaker opens after 5 consecutive failures and pauses requests for 60 seconds.
- Controlled concurrency uses a semaphore, default `POLYGON_MAX_CONCURRENT_REQUESTS=10`.
- There is no free-tier artificial serial delay in the current client.
- Cache reads/writes go through `backend/services/cache.py`.
- `POLYGON_DEBUG=true` enables more verbose provider diagnostics.

News also has optional sources:

- Finnhub via `FINNHUB_API_KEY`.
- Alpha Vantage via `ALPHA_VANTAGE_KEY`.
- Yahoo/Google/MarketWatch RSS paths if `feedparser` is installed. `feedparser` is not in current requirements, so those RSS paths currently log and return empty when missing.
- Sentiment uses FinBERT if `transformers` and `torch` are installed; current requirements do not include them, so it falls back to a lexicon analyzer.

## Universe Builder

The scanner no longer relies only on a fixed stock list when the universe table is populated. `backend/services/universe/universe_builder.py` builds a dynamic stock universe.

Configuration defaults:

- `UNIVERSE_NASDAQ_SIZE=500`
- `UNIVERSE_NYSE_SIZE=300`
- `UNIVERSE_LOOKBACK_DAYS=730`
- `UNIVERSE_REFRESH_CRON=weekly`

Build process:

1. Fetch eligible tickers:
   - NASDAQ: `/v3/reference/tickers?market=stocks&type=CS&exchange=XNAS&active=true&limit=1000`
   - NYSE: `/v3/reference/tickers?market=stocks&type=CS&exchange=XNYS&active=true&limit=1000`
   - Pagination follows `next_url`.
   - Only `type=CS` symbols are retained.
2. Fetch grouped daily bars:
   - For every calendar day in the lookback window, call `/v2/aggs/grouped/locale/us/market/stocks/{date}?adjusted=true`.
   - Missing/empty days are skipped and logged, which covers weekends and market holidays.
   - Requests run concurrently up to `POLYGON_MAX_CONCURRENT_REQUESTS`.
3. Rank:
   - Keep only eligible NASDAQ/NYSE symbols.
   - Compute average daily volume from accumulated grouped bars.
   - Rank NASDAQ and NYSE separately.
   - Take top configured counts.
4. Save:
   - `UniverseSymbol.query.delete()` plus `bulk_save_objects(records)` runs inside one DB transaction.
   - If the transaction fails, the session rolls back.
   - This is transactional delete/insert, not a separate batch table swap.

Operational hooks:

- CLI: `flask --app backend.app rebuild-universe`
- API: `GET /api/universe/status`
- Scheduler: `ENABLE_UNIVERSE_REFRESH_SCHEDULER=true` schedules rebuild jobs through RQ.

If `universe_symbols` is empty or unavailable, scanner falls back to the previous fixed stock universe and logs a warning. It does not silently scan zero symbols.

## Scan System

Primary service: `backend/services/scans.py`.

Markets:

- `stocks`
- `crypto`

Fallback symbol lists:

- Stocks: 80 symbols split as 50 NASDAQ + 30 NYSE in code.
- Crypto: 15 provider symbols, preserving `X:` where needed.
- Stocks use `universe_symbols` first when the dynamic universe has rows.

Available scan filter categories:

| Category | Filters |
|---|---|
| Oscillators | `rsi_oversold`, `rsi_overbought`, `stoch_oversold`, `stoch_overbought` |
| Moving averages | `ema_golden_cross`, `ema_death_cross`, `price_above_sma200`, `macd_bullish`, `macd_bearish` |
| Volatility | `bb_squeeze`, `bb_breakout` |
| Patterns | `bullish_pattern`, `bearish_pattern`, `chart_pattern_bullish` |
| Fibonacci | `near_fib_support`, `near_fib_resistance`, `fib_golden_zone`, `fib_shallow_retrace`, `fib_deep_retrace`, `fib_uptrend`, `fib_downtrend`, `fib_confluence_zone` |

Presets:

- `bullish_momentum`
- `bearish_reversal`
- `oversold_bounce`
- `trend_following`
- `fib_golden_pocket`
- `fib_confluence_play`

Pattern filters inside bulk scans are numeric/TA-style detections from `TechnicalAnalysis.detect_candlestick_patterns` and `TechnicalAnalysis.detect_chart_patterns`. They do not call YOLOv8. YOLOv8 is only used by the single-chart pattern detection flow.

The scanner computes:

- SMA, EMA, RSI, MACD, Bollinger Bands, Stochastic.
- Fibonacci retracements, extensions, trend, zones, nearest support/resistance.
- Candlestick patterns: Doji, Hammer, Inverted Hammer, Shooting Star, Bullish/Bearish Engulfing, Morning Star, Evening Star.
- Chart patterns: Double Bottom, Double Top, Ascending Triangle, Descending Triangle, Bullish Flag.
- Trade setup: direction, action, confidence, entry, stop, targets, risk/reward, key supports/resistances.

The scanner requires at least 30 bars per symbol for full analysis. Timeframe fetch windows are defined in the canonical timeframe config and are longer for higher-level and pattern-sensitive data.

## Canonical Timeframes

`backend/market_config.py` is the backend single source of truth. Timeframe strings are case-sensitive. `1m` means one minute and `1M` means one month.

`/api/filters` returns these timeframes to the frontend; the scan filter panel and chart modal read from that API response rather than keeping a separate hardcoded list.

| Timeframe | Polygon multiplier | Polygon timespan | Category |
|---|---:|---|---|
| `1m` | 1 | minute | intraday |
| `5m` | 5 | minute | intraday |
| `15m` | 15 | minute | intraday |
| `30m` | 30 | minute | intraday |
| `45m` | 45 | minute | intraday |
| `1H` | 1 | hour | intraday |
| `4H` | 4 | hour | intraday |
| `1D` | 1 | day | higher |
| `1W` | 1 | week | higher |
| `1M` | 1 | month | higher |
| `1Y` | 1 | year | higher |

Each internal config includes `days`, `min_bars`, `label`, and `short_label`. The public `/api/filters` timeframe payload exports `label`, `short_label`, `multiplier`, `timespan`, `category`, and the config-driven `available` capability flag; it intentionally does not expose internal lookback fields such as `days` or `min_bars`. The same response now publishes each registered strategy's version, parameter schema, required history and indicators, supported asset classes/timeframes, and availability.

## Pattern Detection

YOLOv8 pattern detection is an on-demand, single-chart feature.

Important deployment model:

- Screen/chart capture happens in the browser.
- The backend does not use `mss` and does not capture the server screen.
- The frontend captures the rendered chart canvas, converts it to base64 JPEG, and posts it to `/api/patterns/detect`.
- The backend decodes the base64 image into a NumPy image buffer and passes that image to the YOLO service.

Backend files:

- `backend/services/patternDetection/yoloService.py`
- `backend/services/patternDetection/signalResolver.py`
- `backend/services/pattern_detection.py`
- `backend/api/pattern_routes.py`

YOLO service behavior:

- Singleton service loaded during app factory startup.
- Model path defaults to `models/yolov8/model.pt`.
- Model URL defaults to the HuggingFace stock-market pattern model.
- `YOLO_AUTO_DOWNLOAD` controls automatic model download.
- `YOLO_CONFIDENCE_THRESHOLD` defaults to `0.50`.
- Input is a NumPy/OpenCV-style image array.
- Output is a list of detections: `{ label, confidence, bbox: [x1, y1, x2, y2] }`.
- Detections below the configured threshold are suppressed.

Signal resolver priority logic:

| Condition | Result |
|---|---|
| YOLO confidence >= threshold and custom deterministic patterns confirm the same pattern | `signal_priority=1`, legacy `source_badge="YOLOv8 + TA-Lib"`, `talib_conflict=false` |
| YOLO confidence >= threshold and custom deterministic patterns are absent/inconclusive | `signal_priority=2`, `source_badge="YOLOv8"`, `talib_conflict=false` |
| YOLO confidence >= threshold and custom deterministic patterns detect a different pattern | `signal_priority=2`, `source_badge="YOLOv8"`, `talib_conflict=true` |
| YOLO confidence < threshold | Suppressed; `signal_priority=null`, no TA-only primary signal |

`POST /api/patterns/detect`:

- Requires auth.
- Rate-limited to 10 requests/minute per user through Redis.
- Accepts `{ image, symbol?, timeframe? }`.
- If symbol and timeframe are present, it fetches the same instrument's market bars and uses the application's custom deterministic pattern analysis as confirmation. There is no external TA-Lib dependency; `talib_*` names and the `YOLOv8 + TA-Lib` badge are legacy labels scheduled for correction in Phase 10.
- Writes an annotated screenshot under `logs/pattern_detections/<user_id>/screenshots/`.
- Appends an XLSX row under `logs/pattern_detections/<user_id>/<YYYY-MM-DD>.xlsx`.
- Response is the full signal payload, or `{ error, signal_priority: null }` on user-facing detection errors.

The current image decode/annotation path uses Pillow and NumPy. OpenCV is still installed for YOLO/Ultralytics compatibility and future image operations.

## Chart System

Frontend charting is implemented in `frontend/src/components/charts/CandlestickChart.jsx`.

Installed charting library:

- `lightweight-charts` declared as `^4.2.1`.
- Lockfile resolves it to `4.2.3`.
- Because this is pre-v5, the current chart uses separate price scales and scale margins rather than native multi-pane support.

Series and indicators:

| Series/indicator | Color source |
|---|---|
| Bullish candles | `CHART_SEMANTIC_COLORS.candleBullish` |
| Bearish candles | `CHART_SEMANTIC_COLORS.candleBearish` |
| Volume | `CHART_SEMANTIC_COLORS.volumeBullish` / `volumeBearish` |
| EMA 9 | `INDICATOR_COLORS.ema9` |
| EMA 20 | `INDICATOR_COLORS.ema20` |
| EMA 50 | `INDICATOR_COLORS.ema50` |
| EMA 200 | `INDICATOR_COLORS.ema200` |
| Bollinger Bands | `INDICATOR_COLORS.bollingerBands` |
| MACD line | `INDICATOR_COLORS.macdLine` |
| MACD signal | `INDICATOR_COLORS.macdSignal` |
| MACD histogram | `INDICATOR_COLORS.macdHistogram*` |
| RSI | `INDICATOR_COLORS.rsi` |
| YOLO pattern overlay | `PATTERN_OVERLAY_COLORS.*` |

Color config lives in `frontend/src/config/indicatorColors.js`. Indicator components import from this file instead of hardcoding hex values.

Organization:

- Candles, EMA lines, and Bollinger Bands render on the main right price scale.
- MACD renders on a separate `macd` price scale with scale margins.
- RSI renders on a separate `rsi` price scale with scale margins.
- Volume uses its own `volume` price scale.
- The chart updates existing series where possible instead of recreating the entire chart on every render.

Legend:

- `frontend/src/components/chart/IndicatorLegend.jsx`
- Rendered as a normal document-flow strip above the chart canvas, not over the plot area.
- Each chip shows color dot, short label, and live value.
- Crosshair move updates live values when possible; otherwise latest values are shown.
- Clicking a chip toggles only that indicator's series.
- Visibility persists in localStorage key `marketScanner.chart.indicatorVisibility.v1`.

Pattern UI:

- "Detect Patterns" button captures visible chart canvases.
- Bounding boxes draw on a canvas layer above the chart.
- Signal badge colors:
  - Legacy `YOLOv8 + TA-Lib` (YOLO plus custom deterministic analysis, not the TA-Lib package): green.
  - `YOLOv8`: blue.
- A custom-deterministic-analysis conflict shows an amber warning icon with tooltip text; response fields still use legacy `talib_*` names.
- Every pattern/signal display includes: "Pattern detection is for research only and does not constitute financial advice."

## Frontend Structure

Routing is defined in `frontend/src/App.jsx` with React Router v6:

| Route | Component | Guard |
|---|---|---|
| `/` | Scanner | Public |
| `/watchlist` | Watchlist | Auth required |
| `/news` | NewsRoom | Auth required |
| `/fundamentals/:symbol` | FundamentalAnalysis | Auth required |
| `/admin` | AdminPanel | Auth required and `role=admin` |

Lazy-loaded routes/components:

- AdminPanel
- NewsRoom
- FundamentalAnalysis
- StockDetailModal

The route-level error boundary is `frontend/src/components/common/RouteErrorBoundary.jsx`.

State:

- Auth state lives in `frontend/src/store/useAuthStore.js`.
- Market, filters, scans, details, watchlist, templates, and notifications live in `frontend/src/store/useMarketStore.js`.
- There is no separate `useWatchlistStore.js` in the current tree.
- Theme state lives in `frontend/src/store/useThemeStore.js`.

Scanner market selection:

- `frontend/src/components/common/Header.jsx` exposes Stocks/Crypto buttons in both desktop and mobile navigation.
- Both choices use the same scanner page. The control sets `useMarketStore.activeMarket`, which supplies the `market` field for search and scan requests.
- This is an asset-class-level toggle only; the current UI does not select NASDAQ versus NYSE, a crypto venue, a pair universe, or an individual symbol for bulk scans.

API client:

- `frontend/src/services/api.js`
- Axios base URL is `${VITE_API_URL}/api`.
- Token key is `access_token` in localStorage.
- Requests attach `Authorization: Bearer <token>`.
- 401 responses clear local auth state and trigger the login modal through the unauthorized handler.
- `VITE_AUTH_DISABLED=true` bypasses auth UI and injects a mock admin user in the frontend.

Search:

- Symbol search uses `AbortController` to cancel stale requests.

Watchlist:

- Stores provider symbols and display symbols.
- Crypto `X:` provider prefixes are preserved in save/retrieve paths.
- Notes are visible and inline editable.
- Duplicate add attempts show a toast.

## Auth and Admin

Auth is not JWT-based in the backend. It uses opaque random tokens:

- `register` and `login` return `access_token` plus user data.
- Token TTL is 7 days.
- Tokens are stored in Redis under `auth:token:{token}`.
- Logout writes `auth:blocklist:{token}` with remaining TTL and deletes the token key.
- Protected routes require `Authorization: Bearer <token>`.

Admin:

- No default admin account is auto-created at normal startup.
- CLI command: `flask --app backend.app create-admin --email <email> --password <password>`.
- Admin routes require `admin_required`.
- Admin panel loads stats, users, scan history, and audit logs independently so one table can show its own load error.
- Updating a user creates an `admin_audit_logs` record.

Auth bypass:

- `AUTH_DISABLED=true` creates/uses a mock admin user path in both frontend and backend.
- Backend ensures a local DB user with id `1` exists for auth-disabled flows.
- This is a development/demo switch and should not be enabled for a real private deployment.

## Database Schema

SQLAlchemy models:

| Model | Table | Notes |
|---|---|---|
| `User` | `users` | Unique `username` and `email`; role constraint `user/admin`; plan constraint `free/premium`; password hash; active flag. |
| `Watchlist` | `watchlists` | User-owned saved symbols; unique `(user_id, symbol)`; stores `symbol`, `provider_symbol`, `display_symbol`, `market`, `notes`. |
| `ScanResult` | `scan_results` | Completed scan matches linked to `user_id` and `job_id`; stores canonical symbol fields, filters, indicators, price, volume, signal. |
| `ScanHistory` | `scan_history` | One row per completed scan with market, timeframe, totals, filters, duration, job id. |
| `ScanTemplate` | `scan_templates` | User-owned named scan criteria JSON. |
| `Notification` | `notifications` | In-app notifications with JSON payload, read state, and dedupe key. |
| `UniverseSymbol` | `universe_symbols` | Dynamic scan universe with `symbol`, `exchange`, `avg_daily_volume`, `rank`, `computed_at`; exchange/rank uniqueness. |
| `AdminAuditLog` | `admin_audit_logs` | Admin action trail. |

Alembic migrations live under `migrations/versions/`. Flask-Migrate is initialized in the factory through `migrate.init_app(app, db)`.

Important constraints:

- Watchlist unique index on `(user_id, symbol)`.
- Enum/check constraints for role, plan, market, and timeframe values.
- `universe_symbols` constrains exchange to NASDAQ/NYSE and rank uniqueness per exchange.

## Environment Variables

Backend:

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | random generated value | Flask secret. Set explicitly in production. |
| `DATABASE_URL` | `sqlite:///market_scanner.db` | SQLAlchemy database URL. Railway should point this to PostgreSQL. |
| `TEST_DATABASE_URL` | `sqlite:///:memory:` | Testing DB URL. |
| `FLASK_ENV` | `production` | Selects config. `development` enables debug. |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated CORS allowlist. |
| `AUTH_DISABLED` | `false` | Development/demo auth bypass. |
| `AUTO_CREATE_SCHEMA` | `false` | If true, calls `db.create_all()` at startup. Prefer migrations. |
| `LOG_LEVEL` | `INFO` | JSON logger level. |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for auth, cache, rate limits, RQ, scan state. |
| `REDIS_CACHE_PREFIX` | `api_cache:` | Redis cache key prefix. |
| `CACHE_MAX_ENTRIES` | `1000` | Cache LRU max entries. |
| `POLYGON_API_KEY` | empty | Required for real market data. |
| `POLYGON_DEBUG` | `false` | Provider debug logging. |
| `POLYGON_MAX_CONCURRENT_REQUESTS` | `10` | Polygon request concurrency cap. |
| `POLYGON_SNAPSHOT_PREFILTER` | `false` | Enables optional snapshot prefiltering. |
| `SCAN_QUEUE_NAME` | `scans` | RQ queue name. |
| `SCAN_JOB_TTL_SECONDS` | `86400` | Redis scan state TTL. |
| `SCAN_JOB_TIMEOUT_SECONDS` | `1800` | RQ job timeout. |
| `SCAN_QUEUE_SYNC` | `false` | Test/dev switch to run scan job inline. |
| `SCAN_DEBUG` | `false` | Scan debug logging. |
| `SCAN_DEBUG_SAMPLE_LIMIT` | `8` | Number of debug samples. |
| `ENABLE_SCAN_TEMPLATE_SCHEDULER` | `false` | Schedule recurring scan-template sweeps. |
| `SCAN_TEMPLATE_EVALUATION_INTERVAL_SECONDS` | `900` | Template sweep interval. |
| `SCAN_TEMPLATE_INITIAL_DELAY_SECONDS` | `60` | First template sweep delay. |
| `SMTP_HOST` | empty | Enables email notification only when configured. |
| `SMTP_PORT` | `587` | SMTP port. |
| `SMTP_USERNAME` | empty | SMTP username. |
| `SMTP_PASSWORD` | empty | SMTP password. |
| `SMTP_FROM` | empty | Notification email sender. Required with SMTP host for email. |
| `SMTP_USE_TLS` | `true` | SMTP TLS toggle. |
| `YOLO_MODEL_PATH` | `models/yolov8/model.pt` | YOLO model location. |
| `YOLO_MODEL_URL` | HuggingFace model URL | Download URL for model. |
| `YOLO_AUTO_DOWNLOAD` | true except testing | Auto-download missing model. |
| `YOLO_CONFIDENCE_THRESHOLD` | `0.50` | YOLO detection threshold. |
| `PATTERN_LOG_ROOT` | `logs/pattern_detections` | XLSX and screenshot log root. |
| `UNIVERSE_NASDAQ_SIZE` | `500` | NASDAQ universe count. |
| `UNIVERSE_NYSE_SIZE` | `300` | NYSE universe count. |
| `UNIVERSE_LOOKBACK_DAYS` | `730` | Universe volume lookback. |
| `UNIVERSE_REFRESH_CRON` | `weekly` | Universe rebuild schedule. Supports `weekly`, `daily`, `hourly`, or seconds. |
| `ENABLE_UNIVERSE_REFRESH_SCHEDULER` | `false` | Schedule universe rebuilds through RQ. |
| `FINNHUB_API_KEY` | empty | Optional news source. |
| `ALPHA_VANTAGE_KEY` | empty | Optional news source. |

Frontend:

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_URL` | empty string | Backend base URL. Axios appends `/api`. |
| `VITE_AUTH_DISABLED` | `false` | Frontend auth bypass/mock admin toggle. |

Docker Compose/local shell variables:

| Variable | Default | Purpose |
|---|---|---|
| `REDIS_PORT` | `6379` | Host Redis port. |
| `BACKEND_PORT` | `5000` | Host backend port. |
| `FRONTEND_PORT` | `5173` | Host frontend port. |

Runtime-provided:

| Variable | Provider | Purpose |
|---|---|---|
| `PORT` | Railway/web host | Gunicorn/Vite preview bind port. |

## Testing and CI

Backend tests:

- Pytest config: `pytest.ini`.
- Test path: `backend/tests`.
- Current backend tests cover:
  - Indicator calculations.
  - Filter logic, cache TTL, auth token service.
  - Register/login/me/watchlist/admin integration routes.
  - Ops health/ready routes.
  - Pattern detection services and route.
  - Polygon retry/timeout behavior.
  - Provider-error handling in scans.
  - Scan templates and notifications.
  - Timeframes.
  - Universe builder.

Frontend tests:

- Vitest/React Testing Library through `npm run test`.
- Tests exist for:
  - Auth store.
  - Market store.
  - FilterPanel.
  - StockDetailModal.
  - WatchlistPage.
  - AdminPanel.

E2E:

- `npm run test:e2e` runs `frontend/e2e/run-e2e.mjs`.
- Spec: `frontend/e2e/user-flow.spec.js`.

CI:

- `.github/workflows/ci.yml` runs on pull requests.
- Secret scan: gitleaks.
- Backend job:
  - Python 3.11.
  - Install `backend/requirements.txt`.
  - Install `ruff`, `pytest`, `pytest-cov`, `pip-audit`.
  - `ruff check backend`.
  - `pytest --cov=backend --cov-fail-under=70`.
  - `pip-audit -r backend/requirements.txt`.
- Frontend job:
  - Node 24.
  - `npm ci`.
  - `npm run lint`.
  - `npm run build`.
  - `npm audit --audit-level=high`.

## Deployment

Railway production shape:

- Backend service from repo root.
- Frontend service from `frontend/`.
- Worker service from repo root.
- PostgreSQL plugin.
- Redis plugin.

Backend:

- Runtime: Python 3.11.9 through `runtime.txt` and `mise.toml`.
- Start command from root `Procfile`: `gunicorn backend.app:app --bind 0.0.0.0:$PORT --timeout 600 --workers 1`.
- Run migrations on deploy with `flask --app backend.app db upgrade` or equivalent Railway pre-deploy command.
- `railpack.json` installs system libraries needed by OpenCV/Ultralytics on Railway minimal images.

Worker:

- Use the same repo and Python dependencies.
- Start command can be `rq worker scans --url $REDIS_URL`.
- If using the RQ scheduler in the worker service, use `rq worker --with-scheduler scans --url $REDIS_URL`.
- Do not replace `$REDIS_URL` with a literal secret in committed files; set it in Railway variables.

Frontend:

- Build command: `npm ci && npm run build`.
- Output directory: `dist/`.
- Production service may use Vite preview or a static host.
- `VITE_API_URL` must be the backend public Railway URL, without `/api`.

Health checks:

- `/health` returns `{ status: "ok", db: "ok", redis: "ok" }` when DB and Redis are reachable.
- `/ready` returns 200 only when DB is reachable and the YOLO model is loaded.
- If the model is missing or cannot load, `/ready` intentionally returns 503.

Docker Compose:

- `docker-compose.yml` defines Redis, backend, worker, scheduler, and frontend.
- The compose backend currently uses SQLite at `backend/instance/market_scanner.db`, not PostgreSQL.
- For production parity, Railway should use PostgreSQL through `DATABASE_URL`.

## Current Versus Stale/Unused

Confirmed current behavior:

- The backend is factory-based, not monolithic.
- Bulk scans are async RQ jobs, not synchronous route work.
- Auth uses Redis-backed opaque tokens, not JWTs.
- Pattern detection accepts client-captured base64 images; no server-side screen capture.
- `mss` is not required for the current YOLO flow.
- `/api/filters` is the backend source of truth for frontend timeframe selectors.
- Crypto provider symbols preserve `X:` before Polygon API calls.

Implemented differently than earlier plans:

- Pattern confirmation uses custom deterministic pattern-analysis output. The current code and UI retain legacy `talib_*` names and a `YOLOv8 + TA-Lib` badge, but there is no external TA-Lib dependency in current requirements; Phase 10 owns the rename and compatibility aliases.
- Universe save is transactional delete/insert in the same table, not a separate staging/batch table swap.
- News and fundamentals are protected by frontend route guards, but the backend endpoints are not token-protected.
- `services/cache.py` still has an in-memory fallback if Redis is unavailable. Redis is preferred, but cache state is not strictly Redis-only in degraded local mode.
- Docker Compose includes a scheduler service in addition to backend, worker, Redis, and frontend.

Stale or cleanup candidates:

- `backend/vendor/opencv_python_stub/opencv_python-4.11.0.86-py3-none-any.whl` exists but is not referenced by current requirements.
- `nixpacks.toml` exists, but current Railway builds shown by the repo are Railpack-oriented through `railpack.json`.
- `frontend/venv` and many `.pyc` files are tracked in git even though `.gitignore` now excludes `venv/` and `*.pyc`.
- Several frontend files contain mojibake text artifacts in rendered copy/icons, for example footer and category labels.
- The scanner `/api/health` payload still reports fallback fixed list counts, not the dynamic universe table count. Use `/api/universe/status` for dynamic universe visibility.
- `AUTH_DISABLED` mock frontend user uses plan `pro`; persisted backend mock user uses DB plan `premium`.

TODO/FIXME scan:

- A source scan for `TODO`, `FIXME`, `XXX`, and `HACK` found no active markers in the scanned project files after excluding generated dependency/output folders.
