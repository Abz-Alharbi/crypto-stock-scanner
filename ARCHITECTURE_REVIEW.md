# Architecture Review — Market Scanner Pro

Review date: 2026-07-11
Method: read-only source inspection with runtime-path tracing. No source, test, configuration, migration, dependency, or existing documentation file was modified. This review and `ARCHITECTURE_IMPROVEMENT_PLAN.md` are the only files overwritten.

---

## 1. Executive Summary

Market Scanner Pro is a Flask + RQ backend with a React/Vite frontend that scans US equities and a small fixed set of cryptocurrencies for technical-analysis signals across eleven canonical timeframes.

Key conclusions, each substantiated in the body of this review:

1. **The required frontend cryptocurrency scan entry point exists, but the product is only partially crypto-aware.** The header toggle (`frontend/src/components/common/Header.jsx:66-80,208-220`) changes `activeMarket`; `runScan` sends `market: 'crypto'` (`frontend/src/store/useMarketStore.js:146-161`); `ScanRequest` accepts it (`backend/schemas/market.py:10,14-34`); and `scan_market` uses it (`backend/services/scans.py:328-336`). The fixed scan can therefore be initiated normally. The first target-capability break is immediately after asset-class selection: neither UI nor request can identify a crypto venue, quote currency, pair, universe, or individual-symbol scan. Backend universe selection then collapses all crypto intent to a hidden 15-pair constant (`scans.py:36-40,336`).
2. **NASDAQ and NYSE are not first-class user-selectable markets, and the combined stock scan is order-biased.** `ScanRequest` has no exchange/universe field (`backend/schemas/market.py:14-18`). Database universe rows are ordered by exchange then rank (`backend/services/universe/universe_builder.py:215-235`), fallback symbols put NASDAQ before NYSE (`backend/services/scans.py:22-42`), and orchestration stops as soon as `max_results` matches have accumulated (`scans.py:381-383`). A broad filter can therefore end a scan before any NYSE symbol is evaluated; the returned set is not a global top-N across both exchanges.
3. **Filters are reusable predicates, not a multi-strategy architecture.** All 22 checks are inline lambdas beside orchestration (`backend/services/scans.py:124-179`). Presets merely select several keys, and a symbol is emitted when *any* one matches (`scans.py:441-490`); there is no ALL/ANY/NOT expression, parameter schema, strategy version, required-history declaration, registry boundary, score/evidence contract, or standalone momentum/ROC implementation. The separately computed `overall_signal` can contradict the selected matched filter (`backend/services/technical.py:756-817`).
4. **Timeframe identity propagates end-to-end, but accepted combinations are not proven correct.** All eleven values survive UI, validation, RQ arguments, provider mapping, persistence, status metadata, and detail/chart requests. The first semantic failure is at capability validation: the API accepts every timeframe for both asset classes and every filter without checking provider entitlement or strategy history. `1M` fetches about 120 monthly bars and `1Y` about 35 annual bars (`backend/market_config.py:115-137`), so 200-bar indicators cannot compute at either interval and the 60-bar chart detector cannot compute at `1Y`; these conditions silently become non-matches.
5. **The universe architecture is structurally equity-specific and operationally fragile.** `UniverseSymbol` restricts exchanges to NASDAQ/NYSE (`backend/models/universe.py:6-19`); the builder hardcodes XNAS/XNYS common stocks and grouped US-stock bars (`backend/services/universe/universe_builder.py:21-24,54-137`). It stores no asset class, venue, pair, quote currency, policy version, source window, or observation coverage. A failed rebuild may replace the current universe with zero rows (`universe_builder.py:174-203`), after which scans silently fall back to 80 constants (`universe_builder.py:215-235`).
6. **TA-Lib support is absent, while the UI claims it exists.** Neither dependency manifest contains TA-Lib. `get_talib_patterns` calls the project's custom `TechnicalAnalysis.full_analysis` (`backend/services/pattern_detection.py:111-117`); actual TA-Lib support is therefore `Unsupported` on every timeframe. The resolver and UI nevertheless display `"YOLOv8 + TA-Lib"` (`backend/services/patternDetection/signalResolver.py:35`; `frontend/src/components/charts/CandlestickChart.jsx:475-501`).
7. **YOLOv8 is reachable but capability-blind and unvalidated.** `PatternDetectRequest` has image, symbol, and timeframe but no asset class (`backend/schemas/patterns.py:9-37`). The stock-market model (`backend/services/patternDetection/yoloService.py:11-14`) receives a browser capture whose theme, zoom, panes, and indicator visibility vary; timeframe is not passed to inference (`backend/services/pattern_detection.py:52-74`). No repository test validates the deployed model by asset class or timeframe.
8. **Displayed indicators can disagree with scan decisions.** Detail cards use backend values, while `CandlestickChart` recomputes EMA, Bollinger Bands, MACD, and RSI (`frontend/src/components/charts/CandlestickChart.jsx:510-639,820-898`). The browser EMA seed differs from pandas `ewm(adjust=False)`, and browser Bollinger Bands use population variance while the backend uses pandas sample standard deviation (`backend/services/technical.py:18-23,58-66`). Chart indicator support is therefore partial even when raw candles render.
9. **The provider transport is directly coupled and only reactively rate-limited.** Scans and universe building import the module-level `polygon` singleton (`backend/clients/polygon.py:359`); no provider or Candle contract exists. Network exceptions and 429s retry, but HTTP 5xx does not (`polygon.py:125-169`); aggregates use one 50,000-row request with no pagination (`polygon.py:208-222`); and the distributed rate-limit helper in `backend/services/rate_limit.py:12-38` is unused.

Required overall classification: **partially crypto-aware**. It is neither frontend-unreachable nor stocks-only, but it is not fully multi-asset. Normal UI users can start a fixed crypto scan, yet NASDAQ, NYSE, and cryptocurrency are not equal first-class markets, actual provider coverage is unverified, and core strategy/timeframe/detector capabilities are incomplete.

---

## 2. Review Scope and Exclusions

In scope: scan orchestration, request schemas, symbol/market models, universes, the Polygon/Massive client, strategy/filter execution, indicators, deterministic and YOLOv8 pattern detection, timeframe handling, chart rendering, scan results and their display, error handling/caching/rate limiting, and the automated tests that cover these.

Excluded per the review brief: authentication, authorization, user accounts, roles/permissions, session management, admin interfaces/APIs/workflows. These are mentioned only where a scan-path route happens to require a token (`@token_required` on `POST /api/scan`, `backend/api/scan_routes.py:50-55`), because that affects whether an anonymous user can reach the scan flow. No auth/admin redesign is proposed anywhere in either document.

Existing repo documents `AUDIT.md` and `IMPROVEMENT_PLAN.md` were noted but not treated as sources of truth; `PROJECT_DOCUMENTATION.md` was read in full and validated against code (Section 5).

---

## 3. Review Method

1. Read `PROJECT_DOCUMENTATION.md` in full. Also read `README.md`, `frontend/README.md`, `RUNBOOK.md`, `AUDIT.md`, the pre-existing `IMPROVEMENT_PLAN.md`, both dependency manifests, CI/deployment configuration, relevant Alembic migrations, DB models, and the frontend e2e specification.
2. Read the complete implementation of: `backend/services/scans.py`, `backend/schemas/market.py`, `backend/schemas/patterns.py`, `backend/market_config.py`, `backend/symbols.py`, `backend/clients/polygon.py`, `backend/services/universe/universe_builder.py`, `backend/services/technical.py`, `backend/services/scan_jobs.py`, `backend/jobs/scan_jobs.py`, `backend/jobs/template_jobs.py`, `backend/services/scan_templates.py`, `backend/services/pattern_detection.py`, `backend/services/patternDetection/yoloService.py`, `backend/services/patternDetection/signalResolver.py`, `backend/api/scan_routes.py`, `backend/api/pattern_routes.py`, `backend/models/scan.py`, `backend/models/universe.py` (and the watchlist model's market constraint).
3. Read the complete frontend scan surface: `frontend/src/App.jsx`, `frontend/src/components/common/Header.jsx`, `frontend/src/components/common/SearchBar.jsx`, `frontend/src/components/filters/FilterPanel.jsx`, `frontend/src/components/stock/ScanResults.jsx`, `frontend/src/components/stock/StockDetailModal.jsx`, `frontend/src/components/TradeSetupCard.jsx`, `frontend/src/store/useMarketStore.js`, `frontend/src/services/api.js`, `frontend/src/components/charts/CandlestickChart.jsx`, and `frontend/src/components/chart/IndicatorLegend.jsx`.
4. Read the directly relevant backend and frontend tests, including timeframe, scan-provider-error, universe, provider-client, indicator/filter, pattern-service/route, integration/store/component, and Playwright e2e tests. Repository-wide searches were used to confirm the absence of a crypto scan test, TA-Lib integration, resampling, momentum strategy, strategy registry, crypto universe provider, and scan-level exchange/venue picker.
5. Traced four representative runtime paths (Sections 7, 8, 12.6, 14) from UI control to displayed result.

Findings are graded: Fully implemented / Partially implemented / Superficial / Missing / Unverified. Provider behavior not evidenced in the repository is marked `Requires external provider verification`.

---

## 4. Files and Components Inspected

| Area | Files |
|---|---|
| Scan orchestration & service | `backend/services/scans.py`, `backend/services/scan_jobs.py`, `backend/jobs/scan_jobs.py`, `worker.py` |
| Request schemas | `backend/schemas/market.py`, `backend/schemas/patterns.py`, `backend/schemas/common.py` (via imports) |
| Routes | `backend/api/scan_routes.py`, `backend/api/pattern_routes.py` |
| Symbols & markets | `backend/symbols.py`, `backend/market_config.py` |
| Universe | `backend/services/universe/universe_builder.py`, `backend/services/universe/__init__.py`, `backend/models/universe.py`, `backend/jobs/universe_jobs.py` (via `worker.py`) |
| Data provider | `backend/clients/polygon.py` |
| Indicators & deterministic patterns | `backend/services/technical.py` |
| YOLOv8 & signal resolution | `backend/services/patternDetection/yoloService.py`, `backend/services/patternDetection/signalResolver.py`, `backend/services/pattern_detection.py` |
| Persistence models | `backend/models/scan.py`, `backend/models/universe.py`, `backend/models/watchlist.py` (market constraint), `backend/models/scan_template.py` (via service) |
| Templates & notifications | `backend/services/scan_templates.py`, `backend/jobs/template_jobs.py` |
| App factory, errors & config | `backend/factory.py`, `backend/app.py`, `backend/config.py`, `backend/errors.py`, `backend/schemas/common.py` |
| Cache, retry & rate limits | `backend/services/cache.py`, `backend/services/rate_limit.py`, `backend/clients/polygon.py`, `backend/tests/test_polygon_client.py` |
| Database migrations | `migrations/versions/f1881463ff5e_initial_schema.py`, `ec83a758dcbd_add_async_scan_job_persistence.py`, `b7c2d9e4a6f1_add_canonical_symbol_fields.py`, `c4f7b820de31_add_scan_templates_and_notifications.py`, `d3a6f1c2b8e9_add_universe_symbols.py`, `e4f2a9b7c6d1_canonical_active_timeframes.py` |
| Frontend shell & routing | `frontend/src/App.jsx` |
| Frontend market/asset selection | `frontend/src/components/common/Header.jsx` |
| Frontend scan controls | `frontend/src/components/filters/FilterPanel.jsx` |
| Frontend search | `frontend/src/components/common/SearchBar.jsx` |
| Frontend results & detail | `frontend/src/components/stock/ScanResults.jsx`, `frontend/src/components/stock/StockDetailModal.jsx`, `frontend/src/components/TradeSetupCard.jsx` |
| Frontend charting | complete `frontend/src/components/charts/CandlestickChart.jsx`, `frontend/src/components/chart/IndicatorLegend.jsx`, `frontend/src/config/indicatorColors.js` |
| Frontend state & API | `frontend/src/store/useMarketStore.js`, `frontend/src/services/api.js` |
| Tests | `backend/tests/conftest.py`, `test_timeframes.py`, `test_scans_provider_errors.py`, `test_universe_builder.py`, `test_polygon_client.py`, `test_indicators.py`, `test_filters_cache_auth.py` (filter/cache portions only), `test_pattern_detection_services.py`, `test_pattern_routes.py`, `test_integration_routes.py` (scan/search portions); `frontend/src/store/useMarketStore.test.js`, `FilterPanel.test.jsx`, `StockDetailModal.test.jsx`, `WatchlistPage.test.jsx` (symbol path only), `frontend/e2e/user-flow.spec.js` |
| Dependencies, CI & docs | `requirements.txt`, `backend/requirements.txt`, `frontend/package.json`, `.github/workflows/ci.yml`, `docker-compose.yml`, `PROJECT_DOCUMENTATION.md`, both README files, `RUNBOOK.md`, `AUDIT.md`, `IMPROVEMENT_PLAN.md` |

Deliberately not inspected: authentication/account/administration implementations and tests except where a shared test file also contains an in-scope scan/filter assertion; generated/vendored/virtual-environment trees; news and fundamentals behavior beyond confirming their direct provider coupling. These exclusions do not leave a gap in the scanner paths reviewed here.

---

## 5. Documentation-versus-Code Discrepancies

`PROJECT_DOCUMENTATION.md` (regenerated 2026-07-08) is broadly consistent with the runtime structure. These material disagreements remain:

| # | Documentation claim | Code reality | Evidence | Significance | Classification |
|---|---|---|---|---|---|
| D-001 | "Each config also includes `days`, `min_bars`, `label`, `short_label`, and `available`" (`PROJECT_DOCUMENTATION.md:234`) | No timeframe entry contains `available`; `public_timeframes()` also omits `days` and `min_bars`, exporting only display/provider mapping fields | `backend/market_config.py:4-139,174-182` | All eleven controls are enabled for both assets because frontend checks only `available === false`; provider/asset limitations cannot be communicated | Documentation outdated / Feature partially implemented |
| D-002 | Pattern provenance is presented as `"YOLOv8 + TA-Lib"` (`PROJECT_DOCUMENTATION.md:269,338`), although the document later says there is no external TA-Lib (`:617`) | Requirements contain no TA-Lib; confirmation calls custom `TechnicalAnalysis.full_analysis` | `backend/services/pattern_detection.py:111-117`; `backend/services/patternDetection/signalResolver.py:15-39`; both requirements manifests | The response, UI, tests, and XLSX logs misstate the detector source | Naming mismatch |
| D-003 | Database table for `Watchlist` is listed as `watchlist` (`PROJECT_DOCUMENTATION.md:422`) | SQLAlchemy and the initial migration use `watchlists` | `backend/models/watchlist.py:7-12`; `migrations/versions/f1881463ff5e_initial_schema.py` (`op.create_table('watchlists', ...)`) | Operational/schema references copied from the document will target the wrong relation | Naming mismatch |
| D-004 | "429 and transient failures retry iteratively" (`PROJECT_DOCUMENTATION.md`, Data Provider transport section) | Timeouts/connection errors and 429 retry. An HTTP 5xx records a failure/circuit state but returns immediately; other `RequestException` values also return without retry | `backend/clients/polygon.py:125-169` | The resilience description overstates upstream HTTP retry behavior | Documentation outdated / Implementation incomplete |
| D-005 | Frontend structure documents routing, state, API, search, and watchlists but omits the stocks/crypto selector | The desktop/mobile Header toggle is the sole asset-class entry point | `frontend/src/components/common/Header.jsx:66-80,208-220` | The only user-facing multi-asset control is absent from the main product documentation | Documentation outdated |

No other material disagreement with `PROJECT_DOCUMENTATION.md` was found. Its fixed 15-pair crypto list, dynamic equity builder, async job flow, canonical timeframe keys, browser-capture YOLO flow, and lack of an actual TA-Lib dependency are accurate descriptions—even where those facts expose architectural gaps.

Other reviewed documentation is materially stale but was not used as authority: `README.md:7,12,70,128,151-170,195-196` describes 80 stocks as the primary universe, only five timeframes, a nonexistent 12.5-second provider delay, a monolithic `backend/app.py`, and a nonexistent frontend `constants/timeframes.js`. The June `IMPROVEMENT_PLAN.md` describes the pre-factory/pre-RQ architecture and is historical rather than current. `frontend/README.md` remains generic Vite template text and documents no product runtime path.

---

## 6. Current-State Architecture Overview

```
React (Vite) SPA
  Header market toggle (stocks|crypto) ─┐
  FilterPanel (timeframe + filters) ────┼─► useMarketStore.runScan ─► POST /api/scan
  SearchBar (per-market ticker search)  │        │ {market, timeframe, filters[], limit}
  ScanResults / StockDetailModal ◄──────┘        ▼
                                    scan_routes.scan → ScanRequest (pydantic)
                                            │
                                    scan_jobs.enqueue_scan_job (Redis state + RQ)
                                            │
                              worker.run_scan_job → jobs.scan_jobs.run_scan_job
                                            │  (Flask app context)
                                    services.scans.scan_market
                              ┌─────────────┼─────────────────┐
                     stocks: universe table │ crypto: CRYPTO_SYMBOLS[15]
                     (fallback 80 symbols)  │
                                            ▼  per symbol, sequential
                        get_bars_with_meta → TIMEFRAME_MAP → polygon.get_aggregates
                                            ▼
                        TechnicalAnalysis.full_analysis (all indicators, fib,
                        candlestick + chart patterns, trade setup, overall signal)
                                            ▼
                        FILTER_DEFINITIONS[key]['check'](analysis) per filter
                                            ▼
                        results[] + ScanResult rows + ScanHistory row
                                            ▼
                        Redis scan_job state → GET /api/scan/status/<id> → UI table
```

Separately: `POST /api/patterns/detect` accepts a browser-captured chart image, runs the YOLOv8 singleton, optionally re-fetches bars for TA confirmation, and resolves a prioritized signal (`backend/services/pattern_detection.py:52-83`). This flow never runs inside bulk scans (asserted by `backend/tests/test_scans_provider_errors.py:88-106`).

---

## 7. End-to-End Equity Scan Trace (verified path)

```text
Header toggle default 'stocks'                Header.jsx:67 / useMarketStore.js:12
→ FilterPanel timeframe buttons               FilterPanel.jsx:74-92 → setTimeframe (useMarketStore.js:67-71)
→ FilterPanel filter checkboxes               FilterPanel.jsx:175-198 → toggleFilter
→ "Run Scan" button                           FilterPanel.jsx:208-224 → runScan
→ request payload {market:'stocks',           useMarketStore.js:156-161
   filters, timeframe, limit:30}
→ POST /api/scan (axios, bearer token)        services/api.js:52; scan_routes.py:50-55 (@token_required)
→ validation: ScanRequest                     schemas/market.py:14-34 (market∈{stocks,crypto}, timeframe∈TIMEFRAME_CONFIG, 1–25 filters, limit≤50)
→ enqueue: scan_jobs.enqueue_scan_job         services/scan_jobs.py:116-155 (Redis state + RQ enqueue of worker.run_scan_job)
→ worker: jobs/scan_jobs.run_scan_job         jobs/scan_jobs.py:14-48 (app context, progress→Redis, cancel check)
→ orchestration: scans.scan_market            services/scans.py:328-681
→ universe: _stock_scan_symbols               services/scans.py:64-67 → universe_builder.get_scan_universe_symbols (universe_builder.py:215-235; DB rows or 80-symbol fallback)
→ provider request: get_bars_with_meta        services/scans.py:70-86 → TIMEFRAME_MAP[tf] {multiplier,timespan,days}
→ candle retrieval: polygon.get_aggregates    clients/polygon.py:208-222 → GET /v2/aggs/ticker/{T}/range/{mult}/{span}/{from}/{to} (cache, retry, circuit breaker, semaphore)
→ indicators/patterns: ta.full_analysis       services/technical.py:716-853 (≥30 bars required)
→ signal resolution: filter lambdas           services/scans.py:441-454; overall_signal from bullish/bearish counts (technical.py:756-817)
→ result schema: results[] entries            services/scans.py:471-490 (canonical symbol fields, price, matched_filters, match_pct, overall_signal, rsi, macd, patterns, trade_setup)
→ persistence: ScanResult + ScanHistory       services/scans.py:492-513,629-643 (market/timeframe CHECK constraints, models/scan.py:10-13)
→ status: Redis state → GET /api/scan/status  scan_routes.py:83-87; useMarketStore.js:167-197 (1 s polling)
→ display: ScanResults table                  ScanResults.jsx:84-227 (signal badge, match %, RSI, patterns, TradeSetupCard)
```

The shared `stocks` path is mechanically complete, but it does **not** prove complete NASDAQ and NYSE scans. The first target break is the request: there is no exchange/universe choice. The second is orchestration fairness: universe rows are NASDAQ-first and the loop breaks on the result cap (`universe_builder.py:218-235`; `scans.py:381-383`), so a broad filter may reach 30 matches before NYSE is visited. Sorting after the loop (`scans.py:645`) cannot repair candidates that were never evaluated. Provider calls and analysis are also sequential; the client semaphore limits concurrency but does not create it in this loop. The SSE endpoint exists (`scan_routes.py:97-119`), while the store polls.

---

## 8. End-to-End Cryptocurrency Scan Trace (begins at the frontend)

```text
Header market toggle → 'crypto'               Header.jsx:66-80 (desktop), 208-220 (mobile) → setMarket('crypto') (useMarketStore.js:65)
→ frontend state: activeMarket='crypto'       useMarketStore.js:12
→ request payload {market:'crypto', ...}      useMarketStore.js:146-161 (same runScan code path as stocks)
→ POST /api/scan                              scan_routes.py:50-55
→ validation: ScanRequest.market='crypto'     schemas/market.py:10 (VALID_MARKETS={'stocks','crypto'}), :20-26
→ scan orchestration: scan_market             services/scans.py:328
→ universe selection: CRYPTO_SYMBOLS          services/scans.py:336 — ★ hardcoded 15 pairs (scans.py:36-40); the dynamic universe path is stocks-only
→ data-provider request: get_bars_with_meta   scans.py:70-86; canonicalize_symbol preserves X: prefix (symbols.py:24-41)
→ candle retrieval: polygon.get_aggregates    clients/polygon.py:208-222 — same aggregates endpoint; crypto vs stock routing is implicit in the "X:" ticker
→ indicator/pattern computation               technical.py:716-853 — asset-agnostic on OHLCV
→ signal resolution: filter lambdas           scans.py:441-454
→ result schema                               scans.py:471-490 with market='crypto'; ScanResult CHECK allows 'crypto' (models/scan.py:11)
→ frontend display                            ScanResults.jsx:150 renders a CRYPTO badge; StockDetailModal/chart work on the X: provider symbol
```

**The fixed-list scan path itself is reachable.** A normal user can toggle to Crypto, pick filters/timeframe, start a scan, and—if the external provider returns usable data—see labeled results. That is stronger than prefix-only or backend-only readiness.

**First concrete break against the required end-to-end capability, starting at the frontend:** after the user clicks Crypto, there is no market/venue/universe/pair/symbol scan control. `activeMarket='crypto'` is the entire context; the request has only `{market,timeframe,filters,limit}` and Pydantic ignores unknown extra fields (`frontend/src/store/useMarketStore.js:146-161`; `backend/schemas/market.py:14-18`; `backend/schemas/common.py:7-8`). The next break is universe construction: `scan_market` unconditionally substitutes the 15-element `CRYPTO_SYMBOLS` constant (`backend/services/scans.py:36-40,336`). Nothing in the scan UI identifies those pairs, their venue/coverage, or the fact that search results cannot be added to the scan universe.

Secondary crypto-path caveats, in order of encounter:

1. **Search** is wired (`SearchQuery.market`; `polygon.search_tickers` sets `market=crypto`, `clients/polygon.py:298-309`), but the searched instrument can only be viewed, never used to scope a scan. The provider search response itself is not covered by a crypto route/integration test.
2. **Candle retrieval for crypto intervals** uses the same fixed calendar-day windows as equities and has no 24/7 session model. Whether the configured Polygon plan returns crypto aggregates, history, or each requested interval is `Requires external provider verification`; repository mocks cannot establish it.
3. **Pattern detection (YOLOv8)** is reachable from a crypto chart with no gating (Section 17).
4. **No test anywhere exercises `scan_market('crypto', …)`** — backend crypto matches cover a search mock and watchlist round-trip, while the frontend's crypto payload test saves a template rather than calling `runScan` (`backend/tests/conftest.py:21-27`; `backend/tests/test_integration_routes.py:38-50`; `frontend/src/store/useMarketStore.test.js:116-138`).

---

## 9. Frontend Asset-Class and Market-Selection Assessment

Explicit determinations required by the brief:

| Question | Determination | Evidence |
|---|---|---|
| Does a control exist to choose stock vs crypto scanning? | **Yes** | `Header.jsx:66-80` (desktop pill toggle), `Header.jsx:208-220` (mobile) |
| Mechanism | Two-button segmented toggle in the global header; not a dropdown/route/page | same |
| Same or separate interfaces for the two markets? | Same interface; only `activeMarket` changes | `useMarketStore.js:65,146-161`; `ScannerPage` in `App.jsx:85-112` has no market-specific branches |
| Does the request payload carry asset-class context? | **Partial** — `market` carries only `stocks` or `crypto`, conflating asset class with market; no exchange, venue, pair, universe, provider, or scan mode follows it | `useMarketStore.js:156-161`; `schemas/market.py:14-18` |
| Can a user initiate a crypto scan without hand-editing an API request? | **Yes** | Trace in Section 8 |
| Can crypto results be represented and displayed correctly? | **Partial** — rows carry `market:'crypto'`, canonical provider/display symbols, and a CRYPTO badge, but UI hardcodes `$` and two decimal places and shows no base/quote currency or venue | `scans.py:471-490`; `ScanResults.jsx:135-155`; `StockDetailModal.jsx:61-72`; `TradeSetupCard.jsx:87-108` |
| Exchange/venue selection (NASDAQ vs NYSE, crypto venue)? | **Missing** — the toggle is binary; the merged stock universe is not filterable per exchange, and the exchange dimension present in `universe_symbols` is never exposed to any API or UI | No route/param found: `ScanRequest` (`schemas/market.py:14-18`) has no exchange/universe field; `/api/universe/status` (`scan_routes.py:27-29`) is status-only |
| Universe/symbol scoping of scans? | **Missing** — scans are always whole-universe; no per-symbol or watchlist-scoped scan exists | `scan_market` signature (`scans.py:328`) takes no symbol subset |
| Strategy availability by asset class? | **Missing** — all filters shown for both markets; no capability metadata in `/api/filters` payload | `scans.filters_payload` (`scans.py:237-251`) returns name/description/category only |
| Timeframe availability by asset class/plan? | **Frontend-only presentation** — UI honors an `available:false` flag the backend never emits (D-1) | `market_config.py:174-182`; `FilterPanel.jsx:28,79` |
| Scan/search state when switching markets? | **Defective** — `setMarket` changes only `activeMarket`; it neither aborts search nor clears/tags results/meta/errors. Header remains switchable during a scan. Current-market copy can relabel an earlier result set, and an earlier search request can populate after the switch | `useMarketStore.js:65,117-143`; `Header.jsx:66-80`; `ScanResults.jsx:48,67` |
| Are unsupported extra request fields rejected? | **No** — the shared Pydantic base uses `extra="ignore"`, so manually supplied `asset_class`, `exchange`, `venue`, or `universe` fields disappear silently | `backend/schemas/common.py:7-8`; `backend/schemas/market.py:14-18` |

---

### Frontend symbol and market-picker details

- The only picker is the global `SearchBar` (`frontend/src/components/common/SearchBar.jsx`). It is **not** equity-restricted: it forwards `activeMarket` to `GET /api/search` (`useMarketStore.js:132`), the backend maps `market=crypto` to Polygon's crypto reference search (`clients/polygon.py:298-309`), the placeholder adapts ("Search crypto… e.g., BTC", `SearchBar.jsx:57`), and results carry a per-item market chip (`SearchBar.jsx:83`).
- Selecting a result opens `StockDetailModal` via `openDetail(provider_symbol)` (`SearchBar.jsx:41-45`) — the picker feeds **detail viewing only**. It has no connection to scan input; there is no way to scan a chosen symbol, a custom list, or a watchlist.
- Frontend validation of crypto symbols is absent. The user never supplies a scan symbol; search accepts arbitrary query text and converts provider results into a detail selection. On API paths that do canonicalize a bare crypto symbol, `canonicalize_symbol` appends `USD` and `X:` (`backend/symbols.py:24-41`), hard-assuming the quote currency.
- The dropdown does not distinguish trading venue, quote currency, or pair variants; Polygon crypto results are shown as flat tickers.

---

## 10. Cryptocurrency Capability Assessment

Per-dimension grading (evidence in parentheses):

| Capability | Status | Evidence |
|---|---|---|
| Crypto-aware frontend request contract | Fully implemented | `useMarketStore.js:156-161` sends `market` |
| Backend crypto request contract | Fully implemented | `schemas/market.py:10,20-26` |
| Crypto endpoint selection | Partially implemented | Aggregates share one endpoint keyed by `X:` prefix (`polygon.py:208-222`); crypto snapshot endpoint exists but only for the optional prefilter (`polygon.py:284-289`, gated by `POLYGON_SNAPSHOT_PREFILTER`) |
| Crypto market-data path | Partial / Unverified externally | A shared code path exists, but actual entitlement, history, venue coverage, and all spans are `Requires external provider verification` |
| Crypto symbol normalization | Partially implemented | `symbols.py:24-41` — works for USD pairs; hardcodes `USD` quote, no base/quote model |
| Crypto candle retrieval | Partial | Same one-page `get_aggregates` implementation; no aggregate pagination, gap validation, incomplete-candle handling, or live crypto evidence (`polygon.py:208-222`) |
| Crypto universe | **Missing** | Only `CRYPTO_SYMBOLS` constant (`scans.py:36-40`); builder and `UniverseSymbol` are equity-only (`universe_builder.py:21-24`, `models/universe.py:9`) |
| Crypto market discovery | Missing (for scans) | `search_tickers` supports crypto but feeds only the detail modal |
| Crypto-compatible scan orchestration | Partially implemented | `scans.py:336` enters a shared loop, but asset variation is a hardcoded conditional and fixed universe; results stop at the first `max_results` matches |
| Crypto-compatible strategies | Partially implemented | Filters are asset-agnostic on the analysis dict, but none declares crypto support and none is validated on crypto data (F-004/F-010) |
| Crypto-compatible timeframe handling | Partially implemented | Same canonical map; equity-tuned `days` windows and calendar assumptions; 24/7 sessions unmodeled |
| Crypto-compatible indicators | Partially implemented | OHLCV math is asset-blind, but capabilities/precision/volume semantics are absent, legitimate zero values become `None` (`technical.py:819-825`), and there is no crypto validation |
| Crypto-compatible chart rendering | Partially implemented | Raw candles render, but formatting is USD/two-decimal oriented and chart indicators use formulas different from backend decisions (`CandlestickChart.jsx:510-639,820-898`) |
| Crypto-compatible pattern detection (deterministic) | Partial / Unverified | Fixed windows/tolerances run mechanically (`technical.py:614-714`), but no asset/timeframe calibration or crypto fixture exists |
| Crypto-compatible TA-Lib detection | **Unsupported** | No dependency or integration; `get_talib_patterns` is custom analysis (`pattern_detection.py:111-117`) |
| Crypto-compatible pattern detection (YOLOv8) | Superficial/ungated | Section 17 |
| Crypto-compatible result schemas | Partially implemented | Persistence has `market`/timeframe, but live result rows omit timeframe, venue, pair/currencies, strategy status/evidence, and insufficient-data outcomes (`scans.py:471-490`; `models/scan.py:11-22`) |
| Crypto-compatible result display | Partially implemented | CRYPTO badge is present, but quote/venue/precision and detector provenance are incomplete |
| Crypto tests | **Missing** for scans | Grep evidence in Section 8, item 4 |
| User-facing crypto scan entry point | **Present** | F-002; Header toggle |
| Crypto scan results | Partial / externally unverified | Code generates matched rows; no live/provider-backed or crypto scan automated test verifies a valid response |

### Frontend cryptocurrency scan entry point (required standalone finding)

**Finding F-002 — Frontend cryptocurrency scan entry point: PRESENT, minimal.** The brief's conditional finding "Missing capability: Frontend cryptocurrency scan entry point" does **not** apply: a reachable control exists (`Header.jsx:66-80` → `setMarket` → `runScan` payload). This conclusion comes from the frontend call chain, not backend inference. Residual gaps: no venue/pair/universe/symbol scan choice; the 15-pair scope is hidden; switching context is racy; and no frontend test performs a crypto `runScan`.

### Required conclusion

The application is **partially crypto-aware**: genuinely reachable from the UI through the shared execution/result code, but built on a hardcoded 15-pair universe without crypto market modeling, capability metadata, validated strategies/timeframes/detectors, or scan tests. It is not stocks-only, not backend-only, and not fully multi-asset. The first concrete break is the missing frontend/request representation for venue, pair, universe, or symbol-scoped crypto intent; the first backend break is fixed universe selection at `backend/services/scans.py:336`.

---

## 11. Strategy and Filter Architecture Assessment

### 11.1 What a "strategy" is today

A filter is a dict entry `{name, description, category, check: lambda analysis -> bool}` inside the nested `FILTER_DEFINITIONS` constant (`backend/services/scans.py:124-179`). Twenty-two filters across five categories. Presets are named filter bundles (`scans.py:193-224`). `scan_market` flattens the dict (`get_flat_filters`, `scans.py:182-187`), validates requested keys, and applies each lambda to the per-symbol analysis output.

### 11.2 Grading against the brief's criteria

| Criterion | Status | Evidence / gap |
|---|---|---|
| Common interface/contract | Partial | Uniform dict shape + `check(analysis)`; no class/Protocol, no type enforcement |
| Registry/discovery | Missing as a mechanism | The dict *is* the registry, but it lives in the orchestration module; no registration API, no plugin path |
| Independently testable | Partial | Lambdas are testable via `get_flat_filters()[key]['check']`; tests exist for filter behavior (`backend/tests/test_filters_cache_auth.py` per pytest layout) but each lambda depends on the full `full_analysis` dict shape |
| Composable | Superficial | Multi-select only counts independent matches. A symbol enters results when **any** selected filter matches (`scans.py:441-468`); there is no explicit ALL/ANY/NOT/grouping/weighting contract. A four-filter preset may return a one-filter match |
| Configurable | Missing | Thresholds (RSI 30/70, stoch 20/80, BB 2 %/-2 %, fib 2 %) are hardcoded in the lambdas; no parameters accepted from the request |
| Decoupled from providers | **Yes** | Lambdas see only the analysis dict; provider access is confined to `get_bars_with_meta` |
| Decoupled from asset class | Yes mechanically | No filter inspects market/symbol; but none *declares* asset applicability either |
| Decoupled from orchestration | No (module-level coupling) | Definitions, presets, universe lists, provider calls, and orchestration all live in `scans.py`; adding a strategy edits the orchestration module even though `scan_market`'s control flow is generic |
| Consistent result schema | Partial | All lambdas return booleans into one row shape, but rows have no strategy version, parameters, direction, score/confidence, explanation/evidence, error, or insufficient-data status (`scans.py:471-490`) |
| Explicit required candle history | **Missing** | Single global gate: `len(bars) < 30 → skip` (`scans.py:404`); yet EMA/SMA-200 need 200 bars (`technical.py:12-23`), chart patterns need 60 (`technical.py:669-672`), MACD needs 35 (`technical.py:46-48`) |
| Explicit supported timeframes | Missing | No filter declares any |
| Explicit supported asset classes | Missing | Same |
| Explicit insufficient-data behavior | Missing/silent | Indicator functions return `None` under min length; lambdas null-check and simply return False — the user cannot distinguish "condition false" from "not computable on this timeframe" |

### 11.3 Hardcoded branches and assumptions found

- Asset-class branch in orchestration: exactly one — `symbols = CRYPTO_SYMBOLS if market == "crypto" else _stock_scan_symbols()` (`scans.py:336`).
- Timeframe-specific assumptions inside strategies: chart-pattern windows (60/20/30 bars) and "200-day SMA" naming assume daily-scale bars; the same bar counts are applied to 1-minute or 1-year bars unchanged (`technical.py:669-714`, filter description "Current price above 200-day SMA", `scans.py:140`).
- **Momentum is not implemented as a strategy or indicator.** The term occurs in preset names/descriptions (`scans.py:193-212`) and unrelated prose/lexicons; no ROC, rate-of-change, or standalone momentum evaluator was found. `bullish_momentum` is only a list of four existing filters.
- Duplicate and divergent indicator logic: signal thresholds appear in `full_analysis` voting and again in filter lambdas (`technical.py:762-799`; `scans.py:126-151`). The browser separately recomputes indicator series. Its EMA seed and Bollinger standard deviation differ from the backend (`technical.py:18-23,58-66`; `CandlestickChart.jsx:820-862`), so visual evidence can disagree with the predicate that selected a result.
- `full_analysis` uses truthiness when serializing indicators, converting legitimate numeric zero values to `None` (`technical.py:819-825`); `test_indicators.py:14-17` proves RSI may validly be zero. Overall signal votes use raw values, while filters consume rounded/presentation values, creating another decision/display seam.
- Backend-detected bearish chart patterns are not selectable: `bearish_pattern` checks candlesticks only, while `detect_chart_patterns` can return Double Top and Descending Triangle (`scans.py:153-159`; `technical.py:685-703`).
- Unknown filter IDs are silently removed when at least one valid key remains (`scans.py:337-340`), because request validation checks list length rather than registry membership (`schemas/market.py:17`). This is incompatible with clear unsupported-combination errors.
- The FilterPanel is data-driven from `/api/filters` (`FilterPanel.jsx:150-204`), a useful base for simple parameterless predicates, but it cannot render parameters, versioning, composition, history/capabilities, detector selection, or validation reasons.

### 11.4 Eager computation

`full_analysis` computes **all** indicators, Fibonacci analysis, both pattern families, and a full trade setup for every symbol on every scan regardless of the selected filters (`technical.py:732-746,828-832`). With ~800 universe symbols this is CPU waste and, more importantly for architecture, prevents any strategy from declaring what it needs.

### 11.5 Conclusion

A new simple boolean filter can be added to `FILTER_DEFINITIONS`, but that edit occurs inside the orchestration module and often also requires changing `TechnicalAnalysis.full_analysis`. A new strategy type—parameterized momentum, cross-symbol ranking, multi-timeframe confirmation, YOLO-in-scan, or a composite expression—cannot be added without modifying orchestration and result handling. The target requirement is therefore **not met**.

### 11.6 Strategy execution trace (required)

```text
User checks "MACD Bullish"                    FilterPanel.jsx:175-198 (key 'macd_bullish' from /api/filters payload)
→ selectedFilters state                       useMarketStore.js:73-80
→ POST /api/scan filters:['macd_bullish']     useMarketStore.js:156-161
→ ScanRequest validates only list size         schemas/market.py:17
→ scan_market intersects known keys            scans.py:337-340 (mixed unknown keys silently dropped; all-unknown → 400)
→ per symbol: ta.full_analysis(bars)          scans.py:423
→ MACD computed: EMA12−EMA26, signal EMA9     technical.py:46-55 (needs ≥35 closes else (None,None,None))
→ lambda check: line > signal (null-guarded)  scans.py:142-143
→ matched_filters / match_pct                 scans.py:441-480
→ result row rsi+macd persisted               scans.py:503-508
→ UI: match bar + RSI cell + signal badge     ScanResults.jsx:157-175
```

---

## 12. Universe Architecture Assessment

### 12.1 Current model

- Schema: `UniverseSymbol(symbol, exchange, avg_daily_volume, rank, computed_at)` with `CheckConstraint("exchange IN ('NASDAQ','NYSE')")` and per-exchange rank uniqueness (`backend/models/universe.py:6-19`).
- Build: reference tickers per exchange (`XNAS`/`XNYS`, `type=CS`, paginated — `universe_builder.py:54-74`, `polygon.py:255-274`) → grouped daily US-stock bars for each calendar day in a 730-day window, fetched concurrently (`universe_builder.py:85-137`) → average over **observed** volume rows → per-exchange rank → top 500/300 → delete-and-insert in one transaction (`universe_builder.py:140-181`). There is no minimum observation count or coverage ratio.
- Consumption: `get_scan_universe_symbols(fallback)` returns rows ordered by exchange+rank or the 80-symbol fallback on empty/error (`universe_builder.py:215-235`); scan-side entry is `_stock_scan_symbols()` (`scans.py:64-67`). Because orchestration stops at the result cap, it may not consume the full ordered list (`scans.py:381-383`).
- Ops: CLI `rebuild-universe`, `GET /api/universe/status` (counts + computed_at only), optional RQ-scheduled refresh (`universe_builder.py:238-303`).
- Resilience/reproducibility: `save_universe` deletes current rows and can commit an empty build; no nonempty/freshness threshold, staging snapshot, policy version, lookback bounds, provider identity, metric unit, or observation count is persisted (`universe_builder.py:174-203`; `models/universe.py:14-19`). Database rows are persistence, not a versioned reproducible snapshot; no separate universe cache is used.
- Frontend: no universe selection of any kind; the FilterPanel footnote says only "Uses the current backend scan universe" (`FilterPanel.jsx:225-227`).

### 12.2 Equity assumptions vs crypto requirements

| Dimension | Current equity assumption | Crypto reality it cannot express |
|---|---|---|
| Identity | One symbol per listing, keyed by exchange | Trading **pair** (base+quote) per venue; BTC exists as X:BTCUSD, X:BTCEUR, … |
| Eligibility | `type=CS` common stock on XNAS/XNYS | Quote-currency filter (USD/USDT/stablecoin), venue coverage, instrument availability |
| Ranking metric | Average provider field `v` over observed grouped-stock days (`universe_builder.py:114-127`) | A crypto policy must explicitly select metric/unit—e.g. notional liquidity, 24-hour volume, or market capitalization—and verify that the provider actually supplies it; repository evidence is insufficient |
| Calendar | Empty grouped-stock dates are skipped without classifying holiday vs provider failure (`universe_builder.py:104-111`) | A 24/7 policy needs different expected-day/gap rules; venue/session behavior requires external/product confirmation |
| Lookback/coverage | 730 calendar days requested, but average divides only by returned rows and enforces no minimum coverage | Young/incomplete pairs require explicit eligibility and minimum-history policy; current schema cannot record coverage |
| Storage | `exchange` CHECK constraint blocks any non-NASDAQ/NYSE row | Needs venue/asset-class columns or a per-class table |
| Scan scoping | Whole table, both exchanges merged | Needs per-universe selection (also missing for equities) |

### 12.3 Conclusion

The universe architecture is **structurally equity-specific**—not superficially generic. Extending it to crypto requires changing the schema constraint and metadata, introducing a provider/policy contract, verifying a crypto discovery/ranking source, and adding a request-level universe key. The existing crypto snapshot method (`polygon.py:284-289`) proves only that a snapshot endpoint is called; its fields, entitlement, history, venue coverage, and suitability for ranking all `Require external provider verification`. Equities also lack exchange-scoped selection and globally fair top-N evaluation even though exchange is stored.

---

## 13. End-to-End Timeframe Assessment

### 13.1 Propagation trace (required)

```text
1. Frontend control: FilterPanel buttons rendered from /api/filters payload  FilterPanel.jsx:24-29,74-92
2. Frontend state: timeframe ('1D' default)                                 useMarketStore.js:19,67-71
3. Request payload: timeframe field                                         useMarketStore.js:159
4. API route: POST /api/scan                                                scan_routes.py:50-55
5. Validation: case-sensitive membership in TIMEFRAME_CONFIG                schemas/market.py:28-34; market_config.py:151-153 (1m≠1M, tested in test_timeframes.py:27-38)
6. Orchestration: scan_market(…, timeframe, …)                              scans.py:328; carried into job args (scan_jobs.py:142-149)
7. Universe selection: timeframe-independent                                scans.py:336 (correct — universes are not per-timeframe)
8. Market-data request: TIMEFRAME_MAP[tf] → multiplier/timespan/days        scans.py:73-78
9. Provider mapping: /v2/aggs/…/range/{multiplier}/{timespan}/{from}/{to}   polygon.py:208-222; asserted by test_scans_provider_errors.py:125-144
10. Candle retrieval: limit=50000, sort asc, adjusted                       polygon.py:219
11. Aggregation/resampling: NONE — every interval provider-native           no resampling code exists anywhere in backend/services
12. Indicator computation: bar-count based, timeframe-blind                 technical.py (periods are bar counts)
13. Strategy evaluation: timeframe-blind lambdas                            scans.py:124-179
14. TA-Lib pattern detection: ABSENT; custom deterministic patterns instead requirements manifests; pattern_detection.py:111-117; technical.py:614-714
15. YOLOv8: timeframe is not an inference input; used for custom confirmation/logs pattern_detection.py:52-74; CandlestickChart.jsx:313-317
16. Signal resolution: timeframe-independent                                signalResolver.py
17. Result schema: live result rows omit timeframe; completed meta carries it scans.py:471-490,654-680
18. Result storage: ScanResult/ScanHistory rows                             scans.py:492-513,629-641
19. Frontend display: meta.timeframe chip; detail modal selector            ScanResults.jsx:113; StockDetailModal.jsx:85-129 (changeDetailTimeframe re-fetches, useMarketStore.js:239-261)
20. Chart rendering: epoch-ms → epoch-s, sorted                             CandlestickChart.jsx:68-88
```

**Determination:** the canonical string is strongly propagated but is **not a complete first-class capability parameter**. No boundary changes `1m` into `1M`, and the job/provider/persistence path preserves the selected value. The first semantic loss is strategy evaluation: `TechnicalAnalysis.full_analysis(bars)` and filter lambdas receive bars but not timeframe, so they cannot declare, reject, or tune interval-specific behavior (`technical.py:717-852`; `scans.py:423,441-454`). The first representation omission is the live result row (`scans.py:471-490`); timeframe exists only in completed `meta` and DB rows. YOLO inference also receives pixels only. Both asset classes share these gaps.

### 13.2 Weaknesses and break points

1. **Fixed lookback windows** (`days` per timeframe, `market_config.py`) rather than "required bars × interval × session calendar." The configured 3,650-day `1M` request can contain only about 120 monthly buckets, so 200-period EMA/SMA filters cannot compute. The 12,775-day `1Y` request can contain only about 35 annual buckets, so neither 60-bar chart patterns nor 200-period averages can compute. These are structural, not plan-specific, limits (`market_config.py:115-137`; `technical.py:12-23,669-673`).
2. **`min_bars` is decorative for scans**: it feeds only the intraday notice; the actual gate is the hardcoded 30 in `scans.py:404` and `technical.py:719`.
3. **Long-lookback silent degradation**: EMA/SMA-200 and 60-bar chart patterns return `None`/empty, then filters treat that as false. Higher timeframes never receive `data_limit_notice` because that helper returns early for non-intraday values (`market_config.py:164-171`).
4. **No local aggregation**: any interval Polygon's plan rejects simply produces zero bars → `provider_data_unavailable` (`scans.py:610-627`); there is no resample-from-lower-interval fallback. Whether specific plans reject `45m` or intraday history depths: `Requires external provider verification`.
5. **Session/calendar model absent**: incomplete trailing candles are not marked or trimmed; time zones/DST and bar alignment are delegated wholly to the provider; equity sessions and 24/7 cryptocurrency trading use identical calendar-day lookbacks.
6. **Error semantics conflate provider and sufficiency failures**: if every attempted symbol returns either no data or fewer than 30 bars, `provider_only_failure` becomes true and the scan returns `provider_data_unavailable` 502—even when the provider returned real but insufficient bars (`scans.py:571-627`).
7. **Tests prove keys, not real interval support**: `test_timeframes.py` checks the canonical map; `test_scans_provider_errors.py:125-144` checks mocked 1m/5m mappings. No real provider fixture/log verifies any stock or crypto interval.

## 14. Timeframe Support Matrix

Every status cell uses exactly the required vocabulary. “Provider support” means demonstrated behavior of the configured Massive/Polygon plan, not merely construction of a URL. “Charting” includes indicator overlays, not only raw-candle drawing. A separate deterministic-pattern column is included so the absence of actual TA-Lib is not disguised.

| Timeframe | Frontend selection | API validation | Scan orchestration | Stock provider support | Crypto provider support | Candle retrieval | Local aggregation/resampling | Indicator computation | Strategy execution | Deterministic patterns | TA-Lib pattern detection | YOLOv8 detection | Result generation | Charting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `1m` | Supported | Partial | Supported | Unverified | Unverified | Partial | Unsupported | Partial | Partial | Partial | Unsupported | Unverified | Partial | Partial |
| `5m` | Supported | Partial | Supported | Unverified | Unverified | Partial | Unsupported | Partial | Partial | Partial | Unsupported | Unverified | Partial | Partial |
| `15m` | Supported | Partial | Supported | Unverified | Unverified | Partial | Unsupported | Partial | Partial | Partial | Unsupported | Unverified | Partial | Partial |
| `30m` | Supported | Partial | Supported | Unverified | Unverified | Partial | Unsupported | Partial | Partial | Partial | Unsupported | Unverified | Partial | Partial |
| `45m` | Supported | Partial | Supported | Unverified | Unverified | Partial | Unsupported | Partial | Partial | Partial | Unsupported | Unverified | Partial | Partial |
| `1H` | Supported | Partial | Supported | Unverified | Unverified | Partial | Unsupported | Partial | Partial | Partial | Unsupported | Unverified | Partial | Partial |
| `4H` | Supported | Partial | Supported | Unverified | Unverified | Partial | Unsupported | Partial | Partial | Partial | Unsupported | Unverified | Partial | Partial |
| `1D` | Supported | Partial | Supported | Unverified | Unverified | Partial | Unsupported | Partial | Partial | Partial | Unsupported | Unverified | Partial | Partial |
| `1W` | Supported | Partial | Supported | Unverified | Unverified | Partial | Unsupported | Partial | Partial | Partial | Unsupported | Unverified | Partial | Partial |
| `1M` | Supported | Partial | Supported | Unverified | Unverified | Partial | Unsupported | Partial | Partial | Partial | Unsupported | Unverified | Partial | Partial |
| `1Y` | Supported | Partial | Supported | Unverified | Unverified | Partial | Unsupported | Partial | Partial | Unsupported | Unsupported | Unverified | Partial | Partial |

Evidence for every non-`Supported` cell (each rule applies to every row carrying that status):

- **API validation — Partial (all):** canonical membership and case are enforced (`schemas/market.py:28-34`; `test_timeframes.py:27-38`), but every interval is accepted for both assets and every filter. There is no provider/asset/strategy capability cross-check, and unknown extra context is ignored (`schemas/common.py:7-8`).
- **Stock provider support — Unverified (all):** mappings and URL construction exist, but no live fixture, contract test, or repository log proves the configured plan's interval, history, entitlement, or delay behavior. `Requires external provider verification`.
- **Crypto provider support — Unverified (all):** there is no real crypto aggregates test or log for any interval. Symbol prefix and a mock returning generic bars do not establish provider support. `Requires external provider verification`.
- **Candle retrieval — Partial (all):** `get_bars_with_meta` calls one aggregate request and extracts OHLCV, but has no aggregate pagination, gap detection, alignment validation, incomplete-candle marker, or asset calendar (`scans.py:70-86`; `polygon.py:208-222`).
- **Local aggregation/resampling — Unsupported (all):** no resample/downsample/aggregate-bars implementation was found; all canonical intervals depend on provider-native output.
- **Indicator computation — Partial (all):** functions run on generic bars, but history requirements vary from 15 to 200 while only a 30-bar global gate exists; interval/asset semantics are undeclared; legitimate zeroes can be serialized as `None`; frontend formulas differ (`technical.py:12-71,717-825`; `CandlestickChart.jsx:820-898`). At `1M` and `1Y`, the configured windows cannot supply 200 native calendar bars.
- **Strategy execution — Partial (all):** predicates execute, but receive no timeframe or asset context, have no supported-timeframe/history declaration, treat insufficient input as false, and use implicit-any composition (`scans.py:124-179,404-454,468`).
- **Deterministic patterns — Partial (`1m`–`1M`):** custom detectors run fixed bar windows/tolerances with no asset/timeframe validation (`technical.py:614-714`). **Unsupported (`1Y`):** the 12,775-day fetch window can contain only about 35 annual buckets, below the 60-bar chart-pattern requirement (`market_config.py:127-137`; `technical.py:669-673`). Candlestick detection still runs; the status grades the requested pattern subsystem as a whole.
- **TA-Lib pattern detection — Unsupported (all):** TA-Lib is absent from both requirements manifests and never imported. The `talib`-named path calls custom analysis (`pattern_detection.py:111-117`).
- **YOLOv8 detection — Unverified (all):** fake-model unit tests and one fake 1D route test prove plumbing only. Timeframe never enters model inference, chart captures vary with viewport/theme/visible overlays, and no deployed-model validation by interval or asset exists (`yoloService.py:139-151`; `test_pattern_detection_services.py`; `test_pattern_routes.py:23-71`).
- **Result generation — Partial (all):** matched rows can be produced, and completed meta/DB rows retain timeframe, but live rows omit timeframe and per-strategy status/evidence; insufficient symbols are skipped/counted, not returned (`scans.py:404-420,471-490,654-680`; `models/scan.py:22,52`).
- **Charting — Partial (all):** raw OHLCV candles render for any returned timestamps, but decision-bearing indicator overlays are independently and differently calculated, and asset-specific currency/precision/session semantics are absent (`CandlestickChart.jsx:68-102,510-639,820-898`).

---

## 15. End-to-End User Capability Matrix

This matrix evaluates the normal UI, not theoretical backend extensibility. Status cells use only `Complete`, `Partial`, `Missing`, or `Unverified`.

| User step | NASDAQ | NYSE | Cryptocurrency |
|---|---|---|---|
| 1. Reach scan interface | Complete | Complete | Complete |
| 2. Select asset class | Complete | Complete | Complete |
| 3. Select market/exchange/venue/universe | Missing | Missing | Missing |
| 4. Search or select an instrument for the scan | Partial | Partial | Partial |
| 5. Select a timeframe | Complete | Complete | Complete |
| 6. Select one or more strategies | Partial | Partial | Partial |
| 7. Start the intended market scan | Partial | Partial | Complete |
| 8. Receive a valid provider-backed response | Unverified | Unverified | Unverified |
| 9. Interpret bullish/bearish/neutral/insufficient-data outcomes | Partial | Partial | Partial |
| 10. View the relevant chart and indicators | Partial | Partial | Partial |
| **Overall** | **Partial** | **Partial** | **Partial** |

Evidence by row:

- Rows 1–2: `/` renders one shared scanner and Header exposes Stocks/Crypto (`App.jsx:85-112,182-184`; `Header.jsx:66-80`).
- Row 3: no exchange, venue, universe, or pair selector/request field exists (`schemas/market.py:14-18`; `FilterPanel.jsx`).
- Row 4: search is asset-aware and opens detail, but cannot scope a scan and does not distinguish NASDAQ from NYSE (`SearchBar.jsx:41-45`; `useMarketStore.js:118-143`).
- Row 5: all eleven controls are selectable (`FilterPanel.jsx:74-92`; `FilterPanel.test.jsx:74-80`), although combination correctness is assessed separately in the timeframe matrix.
- Row 6: parameterless filter checkboxes/presets are selectable, but composition, parameters, capability reasons, Momentum, YOLO-as-strategy, and insufficient-data behavior are missing.
- Row 7: Stocks always means the combined ordered universe, and early result-limit exit may never reach NYSE (`universe_builder.py:215-235`; `scans.py:381-383`). Crypto starts the fixed-list scan normally.
- Row 8: async request/status plumbing exists, but no live provider evidence was run or stored in the repository; all actual provider-backed outcomes remain `Unverified`.
- Row 9: the UI displays basic `overall_signal`, yet that independent vote may disagree with matched filters, and insufficient-data symbols are omitted (`technical.py:756-817`; `scans.py:404-420`; `ScanResults.jsx:73-82`).
- Row 10: raw candles and cards render, but frontend indicator formulas can disagree with backend decisions; crypto currency/precision/venue semantics are incomplete.

No asset class is `Complete`: equities lack selectable exchange/universe scope and fair full-market evaluation; crypto lacks selectable pair/venue/universe scope and verified provider/cross-asset behavior.

---

## 16. Pattern Detection and YOLOv8 Assessment

### Current implementation

- Deterministic detection (`technical.py:614-714`): 7 candlestick + 5 chart patterns; runs inside every scan and in `full_analysis`; drives the `bullish_pattern`/`bearish_pattern`/`chart_pattern_bullish` filters. Never uses YOLO (asserted: `test_scans_provider_errors.py:88-106`).
- Actual TA-Lib: **not found**. Neither requirements manifest contains it and no module imports it. `get_talib_patterns` is a misleading name for custom deterministic output (`pattern_detection.py:111-117`).
- YOLOv8 (`yoloService.py`): singleton, model auto-downloaded from `https://huggingface.co/foduucom/stockmarket-pattern-detection-yolov8` (`yoloService.py:13`), 0.50 confidence threshold, browser-captured chart images only (`pattern_detection.py:52-108`), authenticated + Redis rate-limited endpoint (`pattern_routes.py:12-23`, `pattern_detection.py:188-207`).
- Resolution (`signalResolver.py:15-64`): YOLO detections above threshold become candidates; exact normalized-label equality with custom patterns upgrades priority to 1 and badge to "YOLOv8 + TA-Lib"; any different custom label sets `talib_conflict`; below-threshold YOLO yields an empty signal. The resolver has no pattern ontology and returns priority/pattern/confidence, not bullish/bearish direction. Custom detection alone never becomes a primary result in this endpoint.
- Frontend: "Detect Patterns" button on any chart, overlay boxes scaled from capture size, conflict warning, disclaimer (`CandlestickChart.jsx:302-332,125-172`; badge/behavior confirmed against store/docs).

### Assessment against the brief

| Concern | Finding |
|---|---|
| Training-domain mismatch | The configured model source is explicitly stock-market pattern detection. The repository contains no crypto or per-timeframe evaluation data. Any generalization to crypto is an unverified distribution shift and must not be assumed. |
| Asset-class capability declaration | **Missing** — `PatternDetectRequest` (`schemas/patterns.py:9-37`) accepts any symbol; no market check anywhere in `pattern_detection.py` |
| Chart-rendering consistency | `captureVisibleChart` composites the currently rendered chart canvases. Viewport, zoom, theme colors, visible indicators/panes, and history span are uncontrolled (`CandlestickChart.jsx:302-317,403-451`); no canonical capture contract or server-rendered chart exists |
| Timeframe sensitivity | Timeframe is metadata only; the model sees pixels. No per-timeframe thresholds or validation |
| Confidence/false-positive controls | Single global threshold (0.50) via env; no per-class, per-asset, or per-timeframe calibration |
| TA/YOLO separation | Raw sources and conflict flags are separate in the response (`pattern_detection.py:76-83`), but naming falsely calls custom deterministic analysis TA-Lib and the endpoint never emits deterministic-only output |
| Disagreement behavior | Any nonmatching custom pattern sets conflict, even when labels may be semantically related; YOLO still wins at priority 2 (`signalResolver.py:25-39`) |
| Signal semantics | Resolver returns no bullish/bearish direction, explanation, detector version, threshold used, or calibrated class confidence; it cannot directly satisfy the scan strategy result contract |
| Frontend presentation | Badge + confidence + conflict icon + persistent disclaimer — adequate, except the "TA-Lib" misnomer (D-2) |

### Recommendation (tied to findings F-007)

- **Near-term role:** keep YOLOv8 as an on-demand, single-chart research aid for **equities only**. Enforce the capability server-side and disable the button from shared capability metadata on crypto. Continue showing custom deterministic patterns separately; do not relabel them as YOLO fallback or TA-Lib.
- **Conditions before enabling for crypto:** a versioned, labeled crypto evaluation set rendered under a canonical capture specification; coverage across intended timeframes/venues; per-class precision/recall and false-positive measurements; calibrated thresholds; recorded detector/model version; and an explicit product acceptance threshold. Retraining or fine-tuning is required if validation fails.
- **Long-term role:** one optional detector behind a capability-declaring `PatternDetector` interface alongside—not replacing—deterministic detectors. Normalize pattern ontology and direction, preserve detector-specific evidence/confidence, and stabilize input with either canonical client capture or server-side rendering.

---

## 17. Market-Data Provider Gaps (Massive/Polygon)

Assessed strictly from repository evidence; items the repo cannot prove are marked.

| Dimension | Stocks | Crypto | Evidence / verification status |
|---|---|---|---|
| Aggregates endpoint | `/v2/aggs/ticker/{T}/range/…` | Same endpoint, `X:`-prefixed ticker | `polygon.py:208-222` |
| Symbol format | Plain ticker | `X:BASEQUOTE` composed by `canonicalize_symbol` (USD hardcoded) | `symbols.py:24-41` |
| Reference/universe data | `/v3/reference/tickers?market=stocks&exchange=…` + grouped daily `/v2/aggs/grouped/locale/us/market/stocks/{date}` | Reference search `market=crypto` only; **no grouped-daily equivalent used**; snapshot `/v2/snapshot/locale/global/markets/crypto/tickers` exists but only for the optional prefilter | `polygon.py:255-289,298-309` |
| Supported intervals & history depth | All 11 mappings are requested | Same mappings are requested | No repository evidence proves actual support, history, or plan entitlement for either asset: `Requires external provider verification` |
| Aggregation limit / pagination | Aggregate request uses `limit=50000`; no `next_url` loop | Same | Reference ticker pagination is implemented (`polygon.py:255-274`); aggregate pagination/truncation behavior is not (`polygon.py:208-222`) and `Requires external provider verification` |
| Rate limits / retry | Network timeout/connection failures and 429 retry up to three times; 429 honors `Retry-After`; circuit breaker and process-local semaphore | Shared | HTTP 5xx is not retried; final 429 becomes generic `http_error`; cross-worker Redis helper is unused (`polygon.py:125-169`; `services/rate_limit.py:12-38`) |
| Caching | Successful GET JSON cached with default 300-second TTL through Redis or in-memory fallback | Shared | Cache policy is endpoint/timeframe agnostic; `_snapshot_indexes` remains in process without expiry once loaded (`cache.py:9,38-87`; `polygon.py:37,173-188`) |
| Corporate actions / adjustment | Aggregate request always sends `adjusted=true`; no corporate-action model reaches strategy context | Same flag is sent; crypto meaning/effect is not modeled | Provider adjustment semantics by asset: `Requires external provider verification`; dividends endpoint exists outside the scan path (`polygon.py:219,345-356`) |
| Sessions / trading calendar | Empty grouped-stock days are simply skipped; no exchange calendar or regular/extended-session flag | No 24/7 or venue session model | `universe_builder.py:85-137`; `scans.py:70-86` |
| Volume semantics | Builder ranks raw provider `v` averages but stores no unit/coverage | No crypto ranking exists; raw `v` meaning is not declared | Exact stock/crypto units and comparable notional metric: `Requires external provider verification` (`universe_builder.py:114-171`) |
| Market metadata / venue coverage | Reference builder keeps XNAS/XNYS common-stock identity only in universe rows | Search returns flat crypto tickers; base/quote/venue are not parsed or persisted | `polygon.py:255-309`; `models/universe.py:14-19`; `symbols.py:24-41`; provider venue coverage `Requires external provider verification` |
| Missing candles / gaps | Skipped days tolerated; no gap detection in scan bars | Same | `universe_builder.py:104-111`; no gap logic in `scans.py` |
| Real-time vs delayed | Not addressed; scans use end-of-window aggregates | Same | — ; plan latency: `Requires external provider verification` |
| Error handling surfaced to UI | `provider_not_configured` (503), `provider_data_unavailable` (502), and intraday notices | Shared | All-insufficient data is mislabeled provider unavailable; async job flattens structured errors to a string (`scans.py:571-627`; `jobs/scan_jobs.py:43-48`) |
| Frontend-visible limitations | No provider/plan capability metadata; footer shows fallback counts | Same, plus no venue/pair/precision context | `market_config.py:174-182`; `scans.py:227-251`; `App.jsx:219` |

**Material gap summary:** the client has useful timeout, cache, retry-on-network/429, circuit-breaker, and concurrency primitives, but it remains one concrete singleton with implicit prefix routing, no typed Candle/Instrument contract, no aggregate pagination, no proactive cross-worker quota coordination, and incomplete upstream error semantics. The repository uses no historical crypto universe source. Whether the available reference/snapshot/aggregate endpoints and current plan can supply the required crypto discovery, ranking metrics, intervals, history, venue coverage, latency, and volume semantics all `Require external provider verification`.

---

## 18. Key Architectural Risks and Technical Debt

| ID | Finding (stable IDs referenced by the improvement plan) | Severity |
|----|---|---|
| F-001 | Crypto universe is a 15-symbol constant; no crypto universe construction anywhere (`scans.py:36-40`; builder/model equity-only) | Critical (product goal) |
| F-002 | Frontend crypto scan entry point **exists** but is a bare toggle: no venue/pair/universe context, no disclosure of the 15-pair limit, market-switch can mislabel stale results (`Header.jsx:66-80`; `ScanResults.jsx:48`) | Medium |
| F-003 | Strategies are inline lambdas co-located with orchestration; no contract, registry module, parameters, or versioning (`scans.py:124-179`) | High |
| F-004 | No per-strategy history/timeframe/asset declarations; long-lookback indicators silently `None` → filters silently unmatchable on 1M/1Y and plan-limited intraday (`scans.py:404`; `technical.py:12-23,669-672`) | High |
| F-005 | No capability metadata surface: `/api/filters` carries no per-market/per-timeframe validity; documented `available` flag never emitted (D-1) (`scans.py:237-251`; `market_config.py:174-182`) | High |
| F-006 | Universe schema and builder structurally equity-only (`models/universe.py:9`; `universe_builder.py:21-24`); no exchange/universe scoping in scan requests (`schemas/market.py:14-18`) | High |
| F-007 | Actual TA-Lib is absent while custom confirmation is labeled TA-Lib; YOLOv8's stock-market model is ungated by asset/timeframe and its browser-capture distribution is uncontrolled (`yoloService.py:11-14`; `pattern_detection.py:52-117`; `signalResolver.py:35`) | High |
| F-008 | Timeframe lookbacks are fixed; a global 30-bar gate ignores per-strategy needs; `1M`/`1Y` cannot supply 200 bars; no resampling, calendar, gap, alignment, or partial-candle model; all-insufficient may become a provider 502 (`market_config.py`; `scans.py:404,571-627`) | High |
| F-009 | Direct `polygon` singleton coupling; no provider/Candle interface; prefix-based routing; no aggregate pagination or proactive cross-worker quota limiter; HTTP 5xx not retried (`clients/polygon.py:125-222,359`; `services/rate_limit.py:12-38`) | Medium |
| F-010 | Zero automated coverage of the crypto scan path (backend grep evidence; frontend tests touch crypto only via a template payload, `useMarketStore.test.js:116-138`) | High |
| F-011 | Health payload/footer report fixed fallback counts, not real universe (`scans.py:227-234`; `App.jsx:219`) | Low |
| F-012 | `full_analysis` computes everything for every symbol regardless of selected filters; scan loop is sequential per symbol (`technical.py:716-853`; `scans.py:381`) | Medium |
| F-013 | Documentation drift D-001–D-005 plus materially stale root/frontend README architecture guidance | Low |
| F-014 | Symbol model lacks pair semantics: `canonicalize_symbol` hardcodes USD quote; no base/quote/venue fields anywhere (`symbols.py:24-41`) | Medium |
| F-015 | Live result rows omit timeframe, exchange/venue/pair context, strategy status/evidence, and insufficient-data outcomes; scan status also drops queued market/timeframe/progress detail (`scans.py:471-490,654-680`; `scan_jobs.py:180-188`) | High |
| F-016 | Frontend indicator series use algorithms different from backend scan/card values, and backend truthiness converts legitimate zero indicators to `None` (`technical.py:18-23,58-66,819-825`; `CandlestickChart.jsx:510-639,820-898`) | High |
| F-017 | Request/domain context is under-specified and permissive: `market` conflates asset class/market, unsupported extra fields are ignored, and mixed unknown filter IDs are silently dropped (`schemas/common.py:7-8`; `schemas/market.py:14-18`; `scans.py:337-340`) | High |
| F-018 | NASDAQ-first symbol ordering plus early exit at `max_results` can prevent NYSE evaluation; post-loop sort is not a global top-N (`universe_builder.py:215-235`; `scans.py:381-383,645`) | High |
| F-019 | Universe rebuild has no staging/nonempty/freshness guard and can replace a good universe with zero rows, silently activating the 80-symbol fallback (`universe_builder.py:174-235`) | Medium |
| F-020 | Scan persistence failures are swallowed and structured worker errors collapse to strings; provider/no-data/insufficient-data classifications are not reliable (`scans.py:571-644`; `jobs/scan_jobs.py:43-48`) | Medium |

---

## 19. Target Architecture

Facts above are current state; everything in this section is proposal. The design deliberately preserves: the async RQ job flow, the canonical timeframe map, the pydantic validation layer, the data-driven FilterPanel, the hardened Polygon transport, and the analysis-dict decoupling of filters.

### 19.1 Asset-class abstraction

Introduce a focused `backend/domain/` package because today's `CanonicalSymbol(provider_symbol, display_symbol, market)` cannot express F-014/F-017:

| Concept | Target meaning and boundary |
|---|---|
| `AssetClass` | Enum `EQUITY` / `CRYPTO`; preserve current `stocks` / `crypto` wire aliases during migration. It is classification, not a venue or scan universe. |
| `Asset` | The economic thing, such as a company security or currency/token. This is optional metadata and is not sent to provider endpoints directly. |
| `Instrument` | A tradable identity with stable application ID, asset class, display symbol, currency/precision metadata, provider mappings, status, and venue. Strategies receive this object only when instrument semantics matter. |
| `Market` | Product grouping exposed to users, such as US Equities or Crypto Spot. It declares compatible venues/calendars, not a provider ticker prefix. |
| `Exchange` / `TradingVenue` | Explicit execution/listing venue (`XNAS`, `XNYS`, or a verified crypto venue/aggregate market). `Exchange` may be an equity subtype; domain code uses the broader `TradingVenue`. |
| `TradingPair` | Crypto instrument specialization with required `base_currency` and `quote_currency`; `Symbol` is display/lookup text, not a substitute for pair semantics. |
| `ProviderSymbolMapping` | `(provider_id, instrument_id, provider_symbol, valid_from/to)` at the provider adapter boundary. `X:` never leaks into strategies. |
| `TradingCalendar` / `SessionModel` | Explicit calendar/timezone/session rules: exchange sessions and optional extended hours for equities; verified 24/7 or venue-specific rules for crypto. |
| `AssetCapabilities` | Server-owned declaration of valid `(asset class, market, venue, provider, universe, timeframe, strategy, detector)` combinations plus reasons when unavailable. |

`MarketDataRequest` should contain `instrument_id`, canonical `Timeframe`, requested start/end or required closed-bar count, session policy, adjustment policy, and whether an incomplete candle may be returned. The provider adapter resolves symbols and provider notation. `Candle` should be a typed Pydantic/dataclass value with `start`, `end`, `open/high/low/close`, `volume`, `complete`, `instrument_id`, `timeframe`, and provenance. Preserve numeric price rather than forcing two decimals. Keep volume unit/currency and adjustment semantics explicit in metadata; do not pretend equity share volume and crypto pair volume are interchangeable.

Normalize only what is truly common: ordered OHLCV bars, canonical timeframe identity, data-quality flags, and signal vocabulary. Keep venue, pair currencies, precision, calendar/session, corporate-action adjustment, and volume semantics explicit. This prevents an over-generic abstraction from hiding the exact gaps found in F-006/F-014.

An additive scan command should become:

```text
asset_class, market_id, universe_id OR instrument_ids,
timeframe, strategies[{id, version?, parameters}], result_limit
```

The legacy `market` field remains a compatibility alias initially. Pydantic models should move from `extra="ignore"` to `extra="forbid"` after the compatibility window. A command factory resolves IDs into domain objects and validates the complete combination against `AssetCapabilities`; invalid venue/pair/provider/timeframe/strategy/detector combinations return a structured 422 before an RQ job is created. The same capability document drives the UI, closing F-005/F-017 without duplicating rules.

### 19.2 Strategy and filter model

Replace the inline lambda table with a `backend/strategies/` boundary while preserving all legacy filter IDs for saved templates. In this Python/Pydantic stack, use a structural `Protocol` for evaluator interoperability, frozen dataclasses/Pydantic models for metadata and results, and an abstract base class only where implementations genuinely share lifecycle code. Do not force every strategy to inherit a base class merely to register it.

```python
class Strategy(Protocol):
    definition: StrategyDefinition
    def requirements(self, parameters: BaseModel) -> DataRequirements: ...
    def evaluate(self, context: StrategyContext, parameters: BaseModel) -> StrategyResult: ...

class StrategyDefinition(BaseModel):
    id: str
    version: str
    display_name: str
    description: str
    category: str
    parameter_schema: dict
    supported_asset_classes: set[AssetClass]
    supported_timeframes: set[Timeframe]
    required_data_capabilities: set[str]

class StrategyResult(BaseModel):
    status: Literal["evaluated", "insufficient_data", "unsupported", "error"]
    signal: Literal["bullish", "bearish", "neutral", "no_signal"]
    score: float | None
    confidence: float | None
    explanation: str
    evidence: list[Evidence]
    bars_used: int
```

Required behavior:

- Parameters are validated by a strategy-owned Pydantic schema before enqueue. RSI thresholds, MACD periods, pattern tolerances, and a future Momentum/ROC lookback therefore stop being hardcoded orchestration concerns.
- `DataRequirements` declares minimum closed candles, required fields (OHLC/volume), derived features, session/adjustment needs, and any multi-timeframe inputs. Required history may depend on parameters—for example EMA-200 needs at least 200 closed bars.
- Strategies declare supported assets/timeframes and required provider/data capabilities. Absence becomes `unsupported` or `insufficient_data`, never a false predicate.
- `StrategyContext` contains instrument metadata, canonical timeframe, quality-checked candles, and a lazily computed feature set. It contains no Polygon client or provider symbols, preserving the useful provider-neutral property of today's lambdas.
- A `FeatureEngine` computes one authoritative implementation of EMA/MACD/RSI/Bollinger/pattern features and can return full series for charts. Detail cards, chart overlays, and strategies consume the same versioned output, fixing F-016.
- Composition is an explicit request AST/config (`all`, `any`, `not`, `min_matches`, or weighted score) evaluated by a generic compositor. Presets are named immutable composition configurations, not implicit-any lists. Composition results retain each child result/evidence and resolve direction deterministically.
- Errors are isolated per strategy/instrument and returned as typed status while scan-level infrastructure failures remain scan errors. Confidence is optional and must have defined calibration; it is not invented from arbitrary vote counts.

A `StrategyRegistry` owns registration, duplicate/version checks, discovery, metadata serialization, and factories for configured instances. Modules register at startup through an explicit package loader or Python entry-point configuration; adding a module changes registry configuration/discovery only, never scan orchestration. `scan_market` becomes a generic executor over registry-resolved strategies and a composition tree. `filters_payload`/new `/api/capabilities` is generated from registry metadata, including JSON parameter schemas and incompatibility reasons for the existing data-driven FilterPanel.

Contract tests must run against every registered strategy: parameter validation, declared history, both signal directions plus neutral/no-signal, insufficient data, supported/unsupported asset and timeframe combinations, deterministic evidence serialization, no provider imports, and golden equity/crypto fixtures. A registry test should prove a new standalone Momentum strategy appears in capability metadata and executes without editing orchestration.

### 19.3 Generalized universe model

Share a lifecycle contract, not one ranking formula:

```text
UniverseProvider.describe(universe_id) -> UniverseDefinition
UniverseProvider.build(definition, as_of, provider) -> UniverseCandidateSet
UniverseRepository.publish(candidate_set) -> UniverseSnapshot
UniverseRepository.instruments(snapshot_id) -> ordered Instrument IDs
```

`UniverseDefinition` declares asset class, allowed venues, quote currencies, provider requirements, eligibility policy, ranking policy/version, target size, minimum observations, refresh schedule, maximum staleness, and fallback policy. `UniverseSnapshot` persists immutable `snapshot_id`, as-of/source window, build time, provider ID, policy/version, candidate/selected counts, per-entry metric value/unit/coverage, checksum, and failure diagnostics. A candidate build is staged and validated; an empty, undersized, or stale candidate must not replace the last-known-good snapshot (F-019).

Concrete policies remain asset-specific:

- `NasdaqLiquidityUniverseProvider` and `NyseLiquidityUniverseProvider` can port the current XNAS/XNYS common-stock eligibility and observed daily-volume ranking. A `us_equities_top` definition merges snapshots explicitly. Scanning either evaluates the entire chosen snapshot before applying result limit or uses a documented unbiased candidate policy; exchange-first early exit is removed (F-018).
- `CryptoPairUniverseProvider` discovers explicit trading pairs, filters by verified venue/provider coverage and allowed quote currencies, enforces stablecoin/instrument-status rules chosen by product, then ranks by a verified comparable metric. Candidate metrics may include notional liquidity, 24-hour volume, market capitalization, or spread/depth, but the architecture must not select one until provider fields/units and product policy are confirmed. Different venues/pairs remain distinct Instruments.
- Individual-symbol/custom-list/watchlist scans implement the same `UniverseSelection` result contract without pretending they use a liquidity ranking.

Widen or normalize `universe_symbols` to carry `snapshot_id`, `universe_id`, `instrument_id`, rank, metric value/unit, observation count/coverage, and eligibility metadata; remove the NASDAQ/NYSE-only CHECK after backfill. Cache immutable snapshot reads by snapshot ID and capability metadata by short TTL; persistence remains authoritative. Refresh equity and crypto definitions on independently configured schedules, publish atomically, retain prior snapshots for reproducibility/audit, and alert on stale/failed builds rather than silently switching to constants.

The scan request gains `universe_id` (or explicit `instrument_ids`) and stores the resolved `snapshot_id` in job meta/history. The frontend receives available definitions, counts, as-of time, and limitations from capabilities: All US, NASDAQ, NYSE, and only those crypto pair/venue universes actually verified. This solves equity selection and crypto generalization without forcing identical eligibility rules.

### 19.4 End-to-end timeframe model

- Preserve the proven wire keys (`1m`…`1Y`) but resolve them to an immutable `Timeframe` value with `kind` (`fixed` or `calendar`), canonical label, duration/calendar unit, alignment rule, and closed-bar policy. `1m`–`4H` are fixed-duration; month/year are calendar-aware. Day/week alignment must follow the selected market/session rather than assuming a universal number of seconds.
- Frontend state and `ScanRequest` carry the canonical ID. The validated scan command stores it once; RQ args, market-data requests, strategy context, detector context, result rows/meta, persistence, and chart payload all carry the same value. The result row—not only meta—must include timeframe and data-as-of.
- Provider-specific multiplier/timespan mapping and capability negotiation live solely in the provider adapter. `/api/capabilities` reports native, locally derivable, unavailable, and plan-unverified intervals by asset/market/provider with reasons. Unsupported combinations are rejected before enqueue; an accepted-but-empty provider call is not used as capability discovery.
- Compute lookback from the maximum selected strategy requirement plus warm-up margin and the instrument's calendar. Equity calculation counts eligible sessions/bars and handles exchange holidays/DST; crypto uses its verified 24/7 or venue calendar. Calendar months/years use calendar arithmetic, not fixed seconds. Cap/history limitations yield explicit `insufficient_data` with obtained/required bars.
- Resampling belongs after provider normalization and before feature computation. Aggregate only from a verified finer source with deterministic UTC/venue-session boundaries and OHLCV rules (open first, high max, low min, close last, volume sum with declared unit). Never fabricate `1M`/`1Y` from a duration approximation. Cache keys include instrument, provider, source timeframe, boundaries, adjustment/session policy, and resampler version.
- Normalize timestamps to UTC while retaining venue timezone/session metadata. Detect duplicates, out-of-order bars, gaps, session violations, and provider misalignment. Mark incomplete trailing candles and exclude them from strategy/pattern evaluation unless a strategy explicitly opts in; charts may display them distinctly.
- Strategy and deterministic-detector requirements consume closed, quality-checked bars. YOLO capability declares validated timeframes separately; timeframe plus render/capture version travels with detector results. Signal resolution and result persistence retain detector/strategy version and evidence.
- Remove browser indicator recomputation for decision-bearing series. Return authoritative feature series aligned to the same candles, or share a formally versioned implementation with cross-language golden tests. This closes the current chart/scan contradiction (F-016).

### 19.5 Frontend asset-class and market surface

- Keep the header control as an **asset-class** selector, but make the scanner form hierarchical and explicit: asset class → market/venue → scan mode (`universe`, `single instrument`, or `custom list`) → universe or symbol/trading-pair picker → timeframe → configured strategy instances/composition. Equity choices expose All US/NASDAQ/NYSE only when capabilities advertise them; crypto choices expose verified venues, quote currencies, and pair universes rather than a generic “Crypto” bucket.
- Conditional fields follow capability metadata. A crypto pair picker shows base, quote, venue, status, provider coverage, precision, and display name. Equity search shows exchange. Search selection can populate individual-instrument mode; it is no longer detail-only.
- Fetch a versioned `/api/capabilities` document describing valid asset/market/venue/universe/provider/timeframe/strategy/detector combinations, JSON parameter schemas, counts/freshness, and human-readable unavailability reasons. The backend uses the same registry to validate commands. The UI may cache/render this metadata but must not hardcode business compatibility rules.
- Extend `useMarketStore` with a per-asset draft form and an immutable submitted `scanContext`. Switching asset class aborts stale search, resets/revalidates dependent fields, and either keeps prior results under their original context or clears them deliberately. A running job is always labeled from its submitted/meta context, never current form state (F-002).
- Strategy controls render parameters, composition, required history, and asset/timeframe limitations. Disabled combinations remain visible with explanations; server validation errors map to the relevant field. Search distinguishes loading/no-results/provider-error/invalid combination rather than silently returning an empty list.
- Construct the request from resolved IDs and configured strategies; show a pre-submit summary including universe size/as-of/provider/timeframe. Results label asset class, exchange/venue, pair/base/quote, universe snapshot, timeframe, data-as-of, strategy/detector type/version, signal, score/confidence when defined, and evidence. `insufficient_data`, `unsupported`, and evaluation errors render separately from neutral/no-signal.
- Use instrument currency and precision metadata for prices/trade levels; do not prepend `$` universally. Chart sessions/timezone, gaps/partial bars, and authoritative indicator series match backend evaluation. The Detect Patterns control follows detector capabilities, not only access state.

### 19.6 YOLOv8 capability controls

Introduce a `PatternDetector` contract with detector ID/version, supported asset classes/timeframes, required input (`candles` or canonical rendered image), minimum history, render-spec version, confidence calibration metadata, and typed output (`pattern`, direction, confidence, evidence, status). Keep custom deterministic detection and YOLO as distinct implementations and results.

Near term, capabilities declare the current YOLO model equity-only and only for timeframes that have passed validation; backend rejects unsupported requests and frontend disables them. Rename every TA-Lib field/badge to “deterministic TA” or the exact detector name. If actual TA-Lib is later introduced, it registers as a separate implementation with its own version/tests—it is not inferred from variable names.

Use a canonical capture/render specification or server rendering so theme, panes, zoom, dimensions, candle count, and overlays are controlled. Store render spec, model version, threshold, asset class, venue, timeframe, and data window with every result. When detectors disagree, preserve both results; a resolver may combine them only through a versioned pattern ontology and declared policy. It must not convert exact-label mismatch into an unexplained conflict or let YOLO automatically override deterministic evidence. Unsupported/low-confidence YOLO leaves deterministic output available separately rather than fabricating a combined signal.

Crypto remains disabled until the validation conditions in Section 17 are met; failed validation triggers retraining/fine-tuning or continued equity-only use. Long term, YOLO is supplementary research evidence, not a hidden dependency of bulk deterministic filters.

### 19.7 Provider abstraction

Extract a `MarketDataProvider` Protocol and capability descriptor around the existing client:

```text
capabilities(instrument/market) -> native intervals, history, metadata fields, limits
search(query, asset_class, venue?) -> Instrument candidates
get_candles(MarketDataRequest) -> CandleBatch + provenance/quality/page metadata
list_instruments(market, venue?) -> provider instrument metadata
snapshot(market, venue?) -> typed snapshot rows
```

`PolygonProvider` delegates transport to the existing `PolygonClient`; timeout, cache, circuit-breaker, and retry code is retained and corrected rather than rewritten. A provider factory/DI binding is created once by the app/worker factory and injected into scan, universe, and pattern services. Strategies never receive it. Provider-specific symbols, endpoint paths, pagination, plan errors, adjustment flags, and rate limits terminate in this adapter.

Add contract tests using a `FakeMarketDataProvider`, plus optional keyed provider verification outside normal CI. Implement aggregate pagination/truncation detection, typed errors, 5xx policy, proactive cross-worker quota coordination, endpoint/timeframe-aware caching, expiring snapshots, and observable request/cache/rate metrics. Capability discovery is configuration plus verified provider facts—not trial requests during a scan. This seam directly addresses the singleton/prefix/rate/pagination evidence in F-009.

---

## 20. Recommended Architectural Decisions

1. **ADR-1: Keep `stocks`/`crypto` wire values and filter keys stable** while introducing the domain layer — protects DB CHECK constraints, saved templates (`scan_templates.criteria_json`), and localStorage/frontend state. (Addresses migration risk in F-001/F-003.)
2. **ADR-2: Capability metadata is server-owned and dual-purpose** — the same registry validates requests and feeds the UI (`/api/capabilities` or extended `/api/filters`). Never let the frontend infer validity. (F-005, D-1.)
3. **ADR-3: Strategy registry with declared requirements** replaces `FILTER_DEFINITIONS`; `insufficient_data` becomes a first-class signal. (F-003, F-004, F-015.)
4. **ADR-4: Universe as pluggable providers over a widened table**, with request-level universe selection. (F-001, F-006.)
5. **ADR-5: Computed lookbacks + enforced `min_bars` + optional resampling**, with per-asset-class session calendars. (F-008.)
6. **ADR-6: YOLO gated equity-only until a documented crypto validation passes.** (F-007.)
7. **ADR-7: Provider Protocol seam around the existing client**; no second provider until the seam exists. (F-009.)
8. **ADR-8: Characterization tests before refactoring** — especially a crypto scan test, currently absent. (F-010.)

---

## 21. Open Questions Requiring External or Product Confirmation

1. **Polygon plan coverage** (`Requires external provider verification`): intraday history depth per span; whether `45m` and `year` aggregates return usable data; crypto aggregates entitlement and history depth; crypto snapshot fields available for ranking (notional volume? market cap is likely absent); real-time vs delayed entitlements.
2. **Product**: Should equities be scannable per exchange (the data supports it) — and is the merged behavior intentional? What is the desired crypto universe policy (top-N by what metric, which quote currencies, which venues)? Should scans be scoped to a watchlist/symbol set? Is `1Y` scanning a real use case given ~30-bar requirements imply 30-year listings?
3. **Product/ML**: Is YOLOv8 intended for crypto at all? If yes, who owns building the labeled evaluation set?
4. **Ops**: Is the plan-based timeframe `available` flag (D-1) still wanted, and what should populate it?

---

## 22. Review Limitations

- Read-only static review; no server, worker, or scans were executed, and no live Polygon calls were made. All "works end-to-end" claims are code-trace conclusions corroborated by existing automated tests, not fresh runtime observation.
- `CandlestickChart.jsx` lines ~370–899 (series builders/legend plumbing) were skimmed via targeted greps, not read line-by-line; conclusions about chart timeframe handling rest on the read portion (lines 1–370).
- `backend/factory.py` lines 120–300 (error handlers, headers, YOLO startup, scheduler wiring) were not read in full; doc claims about them were spot-checked only where they intersect scan paths.
- Frontend unit tests other than `useMarketStore.test.js` (FilterPanel, StockDetailModal, Watchlist, Admin tests) were not read; their existence is taken from the file tree.
- News/fundamentals services were assessed only at their provider imports; auth/admin modules were deliberately not reviewed (scope exclusion).
- Provider-plan behavior is unverifiable from the repository and is marked accordingly throughout.

---

## 23. Review Coverage Table

| Review area | Files inspected | Runtime path traced | Evidence included | Status |
|---|---|---|---|---|
| Frontend asset-class selection | `Header.jsx`, `useMarketStore.js`, `App.jsx` | Yes (§8, §9) | Yes | Complete |
| Frontend symbol or market picker | `SearchBar.jsx`, `useMarketStore.js`, `clients/polygon.py` | Yes (§10) | Yes | Complete |
| Scan request construction | `FilterPanel.jsx`, `useMarketStore.js`, `services/api.js` | Yes (§7) | Yes | Complete |
| Scan orchestration | `scan_routes.py`, `services/scan_jobs.py`, `jobs/scan_jobs.py`, `services/scans.py`, `worker.py` | Yes (§7, §8) | Yes | Complete |
| Equity universe | `universe_builder.py`, `models/universe.py`, `test_universe_builder.py` (grep) | Yes (§13) | Yes | Complete |
| Cryptocurrency universe | `scans.py:36-40`; searched `backend/services/universe/` — no crypto implementation exists | Yes (§8, §13) | Yes | Not found (capability missing, inspection complete) |
| Stock data provider | `clients/polygon.py`, `test_polygon_client.py` (existence) | Yes (§7) | Yes | Complete |
| Cryptocurrency data provider | `clients/polygon.py` (shared path, crypto snapshot/search) | Yes (§8) | Yes | Partial — code complete, plan behavior Unverified |
| Strategy execution | `scans.py`, `technical.py`, `test_scans_provider_errors.py` | Yes (§12.6) | Yes | Complete |
| Timeframe propagation | `market_config.py`, `schemas/market.py`, `scans.py`, `polygon.py`, `test_timeframes.py`, frontend selectors | Yes (§14.1) | Yes | Complete |
| TA-Lib (internal TA confirmation) | `technical.py`, `pattern_detection.py`, `signalResolver.py`, `requirements.txt` | Yes (§17) | Yes | Complete (no actual TA-Lib exists — naming only) |
| YOLOv8 | `yoloService.py`, `pattern_detection.py`, `pattern_routes.py`, `schemas/patterns.py`, `CandlestickChart.jsx` | Yes (§17) | Yes | Complete |
| Signal resolver | `signalResolver.py`, `test_pattern_detection_services.py` (existence) | Yes (§17) | Yes | Complete |
| Result schema | `scans.py:471-513,654-681`, `models/scan.py` | Yes (§7) | Yes | Complete |
| Result display | `ScanResults.jsx`, `StockDetailModal.jsx` | Yes (§7, §16) | Yes | Complete |
| Chart system | `CandlestickChart.jsx` (1–370 + greps), `StockDetailModal.jsx` | Yes (§14.1 step 20) | Yes | Partial (lines 370–899 skimmed) |
