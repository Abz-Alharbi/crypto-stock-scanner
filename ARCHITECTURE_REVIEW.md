# Architecture Review — Market Scanner Pro

Review date: 2026-07-11
Method: read-only source inspection with runtime-path tracing. No source, test, configuration, or documentation file was modified. This review and `ARCHITECTURE_IMPROVEMENT_PLAN.md` are the only files created.

---

## 1. Executive Summary

Market Scanner Pro is a Flask + RQ backend with a React/Vite frontend that scans US equities and a small fixed set of cryptocurrencies for technical-analysis signals across eleven canonical timeframes.

Key conclusions, each substantiated in the body of this review:

1. **Cryptocurrency scanning is user-reachable and functional end-to-end, but shallow.** A stocks/crypto toggle exists in the header (`frontend/src/components/common/Header.jsx:66-80`), the scan request carries `market: 'crypto'` (`frontend/src/store/useMarketStore.js:146-161`), the backend validates it (`backend/schemas/market.py:10,20-26`) and executes it (`backend/services/scans.py:336`). However, the crypto "universe" is a hardcoded list of 15 USD pairs (`backend/services/scans.py:36-40`); there is no crypto universe builder, no pair/quote-currency/venue model, no crypto-specific capability metadata, and no automated test exercises a crypto scan. Verdict: **partially crypto-aware** — not superficial, not fully multi-asset.
2. **The frontend cryptocurrency scan entry point exists.** The conditional finding "Missing capability: Frontend cryptocurrency scan entry point" prescribed by the review brief does **not** apply; the entry point was verified by tracing the toggle to a completed request payload. This is recorded as its own finding (F-002) with the residual gaps that remain around it.
3. **Strategy logic is provider-decoupled but not modular.** All 22 filters are inline lambdas in one dict co-located with scan orchestration in `backend/services/scans.py:124-179`. They consume a provider-neutral `analysis` dict (good), but there is no strategy contract, registry, parameterization, versioning, or per-strategy capability/insufficient-data declaration. Adding a strategy means editing the same module that orchestrates scans.
4. **Timeframe is a genuine end-to-end domain parameter.** It survives from the UI through validation, job payload, provider mapping (`backend/market_config.py`), persistence (`ScanResult.timeframe` with a CHECK constraint) and back to display. The weaknesses are: fixed calendar-day lookback windows, a single global 30-bar minimum instead of per-strategy history requirements, long-lookback indicators (EMA/SMA 200, 60-bar chart patterns) silently returning `None` on short-history timeframes, and no local aggregation/resampling fallback.
5. **The universe architecture is structurally equity-specific.** `UniverseSymbol` CHECK-constrains `exchange IN ('NASDAQ','NYSE')` (`backend/models/universe.py:9`), and the builder is wired to US-stock-only Polygon endpoints (`backend/services/universe/universe_builder.py:21-24,276-282` in `backend/clients/polygon.py`). It cannot represent crypto without schema and interface changes.
6. **YOLOv8 pattern detection has no asset-class or capability gating.** The model is the HuggingFace *stock-market* pattern model (`backend/services/patternDetection/yoloService.py:13`), yet the detect endpoint accepts any chart image, including crypto charts, with no domain check and no validation evidence for crypto. The UI badge says "TA-Lib" although TA-Lib is not a dependency.
7. **Provider coupling is direct.** The module-level `polygon` singleton (`backend/clients/polygon.py:359`) is imported by scans, universe, fundamentals, and news services. There is no provider interface; asset-class routing is implicit in the `X:` ticker prefix.

Overall classification against the target capability: **multi-asset in a minimal sense** — a user can scan stocks or crypto on any timeframe with any filter combination, but exchange-level market selection (NASDAQ vs NYSE), crypto universe construction, capability-driven UI, and cross-asset validation are missing.

---

## 2. Review Scope and Exclusions

In scope: scan orchestration, request schemas, symbol/market models, universes, the Polygon/Massive client, strategy/filter execution, indicators, deterministic and YOLOv8 pattern detection, timeframe handling, chart rendering, scan results and their display, error handling/caching/rate limiting, and the automated tests that cover these.

Excluded per the review brief: authentication, authorization, user accounts, roles/permissions, session management, admin interfaces/APIs/workflows. These are mentioned only where a scan-path route happens to require a token (`@token_required` on `POST /api/scan`, `backend/api/scan_routes.py:50-55`), because that affects whether an anonymous user can reach the scan flow. No auth/admin redesign is proposed anywhere in either document.

Existing repo documents `AUDIT.md` and `IMPROVEMENT_PLAN.md` were noted but not treated as sources of truth; `PROJECT_DOCUMENTATION.md` was read in full and validated against code (Section 5).

---

## 3. Review Method

1. Read `PROJECT_DOCUMENTATION.md` in full; also read `requirements.txt`, `pytest.ini` targets, `worker.py`, `backend/config.py`, `backend/factory.py`, DB models, and the frontend e2e spec.
2. Read the complete implementation of: `backend/services/scans.py`, `backend/schemas/market.py`, `backend/schemas/patterns.py`, `backend/market_config.py`, `backend/symbols.py`, `backend/clients/polygon.py`, `backend/services/universe/universe_builder.py`, `backend/services/technical.py`, `backend/services/scan_jobs.py`, `backend/jobs/scan_jobs.py`, `backend/jobs/template_jobs.py`, `backend/services/scan_templates.py`, `backend/services/pattern_detection.py`, `backend/services/patternDetection/yoloService.py`, `backend/services/patternDetection/signalResolver.py`, `backend/api/scan_routes.py`, `backend/api/pattern_routes.py`, `backend/models/scan.py`, `backend/models/universe.py` (and the watchlist model's market constraint).
3. Read the complete frontend scan surface: `frontend/src/App.jsx`, `frontend/src/components/common/Header.jsx`, `frontend/src/components/common/SearchBar.jsx`, `frontend/src/components/filters/FilterPanel.jsx`, `frontend/src/components/stock/ScanResults.jsx`, `frontend/src/components/stock/StockDetailModal.jsx`, `frontend/src/store/useMarketStore.js`, `frontend/src/services/api.js`, and the pattern-detection/indicator portions of `frontend/src/components/charts/CandlestickChart.jsx`.
4. Read tests: `backend/tests/conftest.py`, `test_timeframes.py`, `test_scans_provider_errors.py`, and grepped all backend tests for crypto coverage; read `frontend/src/store/useMarketStore.test.js` (template section) and `frontend/e2e/user-flow.spec.js`.
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
| App factory & config | `backend/factory.py` (lines 1–120), `backend/config.py` |
| Frontend shell & routing | `frontend/src/App.jsx` |
| Frontend market/asset selection | `frontend/src/components/common/Header.jsx` |
| Frontend scan controls | `frontend/src/components/filters/FilterPanel.jsx` |
| Frontend search | `frontend/src/components/common/SearchBar.jsx` |
| Frontend results & detail | `frontend/src/components/stock/ScanResults.jsx`, `frontend/src/components/stock/StockDetailModal.jsx` |
| Frontend charting | `frontend/src/components/charts/CandlestickChart.jsx` (lines 1–370 read; remainder skimmed via grep) |
| Frontend state & API | `frontend/src/store/useMarketStore.js`, `frontend/src/services/api.js` |
| Tests | `backend/tests/conftest.py`, `backend/tests/test_timeframes.py`, `backend/tests/test_scans_provider_errors.py`, grep of all backend tests; `frontend/src/store/useMarketStore.test.js`, `frontend/e2e/user-flow.spec.js` |
| Dependencies & docs | `requirements.txt`, `PROJECT_DOCUMENTATION.md` |

Not inspected in depth (out of scope or peripheral): auth/admin modules, news/fundamentals services beyond their provider imports, migrations, docker/deploy configs, `IndicatorLegend.jsx`, vendored/venv trees.

---

## 5. Documentation-versus-Code Discrepancies

`PROJECT_DOCUMENTATION.md` (regenerated 2026-07-08) is unusually accurate. Material disagreements found:

| # | Documentation claim | Code reality | Evidence | Significance | Classification |
|---|---|---|---|---|---|
| D-1 | "Each config also includes `days`, `min_bars`, `label`, `short_label`, and `available`" (doc §Canonical Timeframes, line 234) | No timeframe entry has an `available` key; `public_timeframes()` exports only `label`, `short_label`, `multiplier`, `timespan`, `category` | `backend/market_config.py:4-139,174-182` | The frontend gates on `config.available !== false` (`FilterPanel.jsx:28`, `useMarketStore.js:68-70`, `StockDetailModal.jsx:26`), so every timeframe is always enabled; the documented plan-based disabling mechanism has no backend producer | Documentation outdated / feature partially implemented (frontend consumer exists, backend producer missing) |
| D-2 | Signal badge documented as "YOLOv8 + TA-Lib" and resolver params named `talib_patterns` | TA-Lib is not a dependency (`requirements.txt` has no `TA-Lib`); "TA" confirmation is the internal `TechnicalAnalysis` output. The doc itself admits this at line 617, yet the user-facing badge string remains `"YOLOv8 + TA-Lib"` | `backend/services/patternDetection/signalResolver.py:35`; `backend/services/pattern_detection.py:111-117` | Misleading provenance label shown to end users; harmless technically | Naming mismatch |
| D-3 | "Auth is not JWT-based" (doc line 393) | Correct in backend, but frontend comments call the token header a "JWT interceptor" | `frontend/src/services/api.js:19` | Cosmetic only | Naming mismatch |
| D-4 | "The scanner `/api/health` payload still reports fallback fixed list counts" (doc line 629) — documented as known issue | Confirmed: `health_payload()` reports `len(ALL_STOCK_SYMBOLS)`=80 and `len(CRYPTO_SYMBOLS)`=15 regardless of the dynamic universe, and the footer renders these numbers | `backend/services/scans.py:227-234`; `frontend/src/App.jsx:219` | Users see "Stocks: 80" while scans may cover ~800 symbols; erodes trust in displayed metadata | Implementation incomplete (doc is accurate; flagged here because it is user-visible) |
| D-5 | Doc §Frontend Structure describes routes, stores, and search but never mentions the header stocks/crypto market toggle | The toggle exists and is the sole asset-class selector | `frontend/src/components/common/Header.jsx:66-80,208-220` | The single most important multi-asset control is undocumented | Documentation outdated (omission) |
| D-6 | "Crypto: 15 provider symbols, preserving `X:` where needed" (doc lines 178–180) | Confirmed exactly | `backend/services/scans.py:36-40` | Doc is honest that crypto is a fixed list; the architectural gap is real, not a doc error | Accurate — recorded for completeness |
| D-7 | Doc table says Patterns category has 3 filters (`bullish_pattern`, `bearish_pattern`, `chart_pattern_bullish`) — implies no bearish chart-pattern filter | Confirmed: `detect_chart_patterns` produces bearish patterns (Double Top, Descending Triangle) but no scan filter exposes "bearish chart pattern" | `backend/services/scans.py:153-160`; `backend/services/technical.py:685-703` | Backend capability exists that no filter (hence no user) can select — an asymmetric bull/bear surface | Feature partially implemented |

No other material disagreement was found; async job flow, Redis keys, universe build steps, YOLO deployment model, and env-var tables match the code.

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

No break points. Notable characteristics: symbols are fetched **sequentially** in the job loop (`scans.py:381`), concurrency exists only inside the HTTP client semaphore; the SSE endpoint exists (`scan_routes.py:97-119`) but the store uses polling.

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

**The path does not break.** A normal user can toggle to Crypto, pick filters and a timeframe, run a scan, and see labeled crypto results.

**First concrete limitation (not a break), starting from the UI:** the *universe-construction* stage. For stocks the orchestrator consults the ranked 800-symbol database universe; for crypto it uses the 15-element constant at `backend/services/scans.py:36-40`. Nothing in the UI communicates this asymmetry — the footer even reports "Crypto: 15" from the fallback counter (`App.jsx:219`, fed by `scans.health_payload`).

Secondary crypto-path caveats, in order of encounter:

1. **Search** works (`SearchQuery.market`, `polygon.search_tickers` sets `market=crypto`, `clients/polygon.py:298-309`), but the searched instrument can only be *viewed*, never added to the scan universe.
2. **Candle retrieval for crypto intervals** uses identical `days` windows tuned for equities; because crypto trades 24/7, bar counts differ materially (e.g. `1H`/90 days ≈ 2,160 crypto bars vs ≈ 585 equity RTH bars). Not incorrect, but the `min_bars`/notice logic assumes one calendar model. Whether the configured Polygon plan actually returns crypto aggregates for all spans: `Requires external provider verification`.
3. **Pattern detection (YOLOv8)** is reachable from a crypto chart with no gating (Section 17).
4. **No test anywhere exercises `scan_market('crypto', …)`** — grep of `backend/tests` for "crypto" matches only the search mock (`conftest.py:21-27`) and a watchlist round-trip (`test_integration_routes.py:38-50`).

---

## 9. Frontend Asset-Class and Market-Selection Assessment

Explicit determinations required by the brief:

| Question | Determination | Evidence |
|---|---|---|
| Does a control exist to choose stock vs crypto scanning? | **Yes** | `Header.jsx:66-80` (desktop pill toggle), `Header.jsx:208-220` (mobile) |
| Mechanism | Two-button segmented toggle in the global header; not a dropdown/route/page | same |
| Same or separate interfaces for the two markets? | Same interface; only `activeMarket` changes | `useMarketStore.js:65,146-161`; `ScannerPage` in `App.jsx:85-112` has no market-specific branches |
| Does the request payload carry asset-class context? | **Yes** — `market` field | `useMarketStore.js:156-161`; `schemas/market.py:15` |
| Can a user initiate a crypto scan without hand-editing an API request? | **Yes** | Trace in Section 8 |
| Can crypto results be represented and displayed correctly? | **Yes** — `market:'crypto'` in each result row; CRYPTO badge; `X:`-prefixed provider symbol drives detail/chart/watchlist | `scans.py:475`, `ScanResults.jsx:135-150,186,194`, `StockDetailModal.jsx:72` |
| Exchange/venue selection (NASDAQ vs NYSE, crypto venue)? | **Missing** — the toggle is binary; the merged stock universe is not filterable per exchange, and the exchange dimension present in `universe_symbols` is never exposed to any API or UI | No route/param found: `ScanRequest` (`schemas/market.py:14-18`) has no exchange/universe field; `/api/universe/status` (`scan_routes.py:27-29`) is status-only |
| Universe/symbol scoping of scans? | **Missing** — scans are always whole-universe; no per-symbol or watchlist-scoped scan exists | `scan_market` signature (`scans.py:328`) takes no symbol subset |
| Strategy availability by asset class? | **Missing** — all filters shown for both markets; no capability metadata in `/api/filters` payload | `scans.filters_payload` (`scans.py:237-251`) returns name/description/category only |
| Timeframe availability by asset class/plan? | **Frontend-only presentation** — UI honors an `available:false` flag the backend never emits (D-1) | `market_config.py:174-182`; `FilterPanel.jsx:28,79` |
| Scan-state preservation when switching markets? | Filters/timeframe persist across toggles (shared store keys); prior results are *not* cleared or relabeled until the next scan, so a user can toggle to Crypto while stock results remain onscreen; per-row `market` badges keep rows truthful, but `activeMarket`-based copy ("Scanned N crypto…", `ScanResults.jsx:48`) can mislabel a previous stock scan | `useMarketStore.js:65` (setMarket sets only `activeMarket`); `ScanResults.jsx:48,67` |

---

## 10. Frontend Symbol and Market-Picker Assessment

- The only picker is the global `SearchBar` (`frontend/src/components/common/SearchBar.jsx`). It is **not** equity-restricted: it forwards `activeMarket` to `GET /api/search` (`useMarketStore.js:132`), the backend maps `market=crypto` to Polygon's crypto reference search (`clients/polygon.py:298-309`), the placeholder adapts ("Search crypto… e.g., BTC", `SearchBar.jsx:57`), and results carry a per-item market chip (`SearchBar.jsx:83`).
- Selecting a result opens `StockDetailModal` via `openDetail(provider_symbol)` (`SearchBar.jsx:41-45`) — the picker feeds **detail viewing only**. It has no connection to scan input; there is no way to scan a chosen symbol, a custom list, or a watchlist.
- Frontend validation of crypto symbols: none needed — the user never types a symbol into a scan; typed search text is passed through as a query string. On the watchlist/API side, bare crypto symbols are normalized by `canonicalize_symbol` (appends `USD`, prefixes `X:`, `backend/symbols.py:24-41`), which hard-assumes a USD quote currency (see F-014).
- The dropdown does not distinguish trading venue, quote currency, or pair variants; Polygon crypto results are shown as flat tickers.

---

## 11. Cryptocurrency Capability Assessment

Per-dimension grading (evidence in parentheses):

| Capability | Status | Evidence |
|---|---|---|
| Crypto-aware frontend request contract | Fully implemented | `useMarketStore.js:156-161` sends `market` |
| Backend crypto request contract | Fully implemented | `schemas/market.py:10,20-26` |
| Crypto endpoint selection | Partially implemented | Aggregates share one endpoint keyed by `X:` prefix (`polygon.py:208-222`); crypto snapshot endpoint exists but only for the optional prefilter (`polygon.py:284-289`, gated by `POLYGON_SNAPSHOT_PREFILTER`) |
| Crypto market-data path | Fully implemented (code path) / Unverified (plan behavior) | Section 8; `Requires external provider verification` for plan coverage of crypto spans |
| Crypto symbol normalization | Partially implemented | `symbols.py:24-41` — works for USD pairs; hardcodes `USD` quote, no base/quote model |
| Crypto candle retrieval | Fully implemented | Same `get_aggregates` path |
| Crypto universe | **Missing** | Only `CRYPTO_SYMBOLS` constant (`scans.py:36-40`); builder and `UniverseSymbol` are equity-only (`universe_builder.py:21-24`, `models/universe.py:9`) |
| Crypto market discovery | Missing (for scans) | `search_tickers` supports crypto but feeds only the detail modal |
| Crypto-compatible scan orchestration | Fully implemented | `scans.py:336` single branch, remainder shared |
| Crypto-compatible strategies | Partially implemented | Filters are asset-agnostic on the analysis dict, but none declares crypto support and none is validated on crypto data (F-004/F-010) |
| Crypto-compatible timeframe handling | Partially implemented | Same canonical map; equity-tuned `days` windows and calendar assumptions; 24/7 sessions unmodeled |
| Crypto-compatible indicators | Fully implemented | Pure OHLCV math (`technical.py`) |
| Crypto-compatible chart rendering | Fully implemented | `CandlestickChart.jsx:68-88` renders any OHLCV series; UTC epoch-seconds time |
| Crypto-compatible pattern detection (deterministic) | Fully implemented (mechanically) / Unverified (tuning) | Thresholds like 3 %/2 % pattern tolerances (`technical.py:669-714`) were not tuned per asset class |
| Crypto-compatible pattern detection (YOLOv8) | Superficial/ungated | Section 17 |
| Crypto-compatible result schemas | Fully implemented | `market` column + CHECK includes crypto (`models/scan.py:11`) |
| Crypto-compatible result display | Fully implemented | `ScanResults.jsx:150` CRYPTO badge; watchlist keeps `X:` symbols (`models/watchlist.py:29`) |
| Crypto tests | **Missing** for scans | Grep evidence in Section 8, item 4 |
| User-facing crypto scan entry point | **Present** | F-002; Header toggle |
| Crypto scan results | Fully implemented | Section 8 |

### Frontend cryptocurrency scan entry point (required standalone finding)

**Finding F-002 — Frontend cryptocurrency scan entry point: PRESENT, minimal.** The brief's conditional finding "Missing capability: Frontend cryptocurrency scan entry point" does **not** apply: a reachable, working control exists (`Header.jsx:66-80` → `setMarket` → `runScan` payload). This was verified independently of backend readiness, by tracing the click handler to the request payload. Residual gaps recorded under this finding: (a) the control is a bare binary toggle with no venue/pair/universe context; (b) nothing in the scan UI reveals that the crypto scan covers only 15 fixed pairs; (c) `activeMarket`-derived copy can mislabel results rendered before a market switch (`ScanResults.jsx:48`).

### Required conclusion

The application is **partially crypto-aware**: genuinely reachable and functional from UI to persisted results, but built on a hardcoded 15-pair universe, without crypto capability metadata, crypto-validated strategies/patterns, crypto tests, or any crypto-specific market model. It is **not** "stocks-only in practice", not "backend-only", and not "fully multi-asset". The first concrete deficiency in the end-to-end flow, walking from the UI inward, is **universe construction** (`backend/services/scans.py:336`).

---

## 12. Strategy and Filter Architecture Assessment

### 12.1 What a "strategy" is today

A filter is a dict entry `{name, description, category, check: lambda analysis -> bool}` inside the nested `FILTER_DEFINITIONS` constant (`backend/services/scans.py:124-179`). Twenty-two filters across five categories. Presets are named filter bundles (`scans.py:193-224`). `scan_market` flattens the dict (`get_flat_filters`, `scans.py:182-187`), validates requested keys, and applies each lambda to the per-symbol analysis output.

### 12.2 Grading against the brief's criteria

| Criterion | Status | Evidence / gap |
|---|---|---|
| Common interface/contract | Partial | Uniform dict shape + `check(analysis)`; no class/Protocol, no type enforcement |
| Registry/discovery | Missing as a mechanism | The dict *is* the registry, but it lives in the orchestration module; no registration API, no plugin path |
| Independently testable | Partial | Lambdas are testable via `get_flat_filters()[key]['check']`; tests exist for filter behavior (`backend/tests/test_filters_cache_auth.py` per pytest layout) but each lambda depends on the full `full_analysis` dict shape |
| Composable | Partial | Multi-select composition is AND-of-matches only in the sense of `matched_filters` counting; a symbol matches if **any** selected filter matches (`scans.py:468`), and ranking is by match percentage — there is no ALL/ANY/NOT expression model |
| Configurable | Missing | Thresholds (RSI 30/70, stoch 20/80, BB 2 %/-2 %, fib 2 %) are hardcoded in the lambdas; no parameters accepted from the request |
| Decoupled from providers | **Yes** | Lambdas see only the analysis dict; provider access is confined to `get_bars_with_meta` |
| Decoupled from asset class | Yes mechanically | No filter inspects market/symbol; but none *declares* asset applicability either |
| Decoupled from orchestration | No (module-level coupling) | Definitions, presets, universe lists, provider calls, and orchestration all live in `scans.py`; adding a strategy edits the orchestration module even though `scan_market`'s control flow is generic |
| Consistent result schema | Yes | Boolean match + shared result row (`scans.py:471-490`) |
| Explicit required candle history | **Missing** | Single global gate: `len(bars) < 30 → skip` (`scans.py:404`); yet EMA/SMA-200 need 200 bars (`technical.py:12-23`), chart patterns need 60 (`technical.py:669-672`), MACD needs 35 (`technical.py:46-48`) |
| Explicit supported timeframes | Missing | No filter declares any |
| Explicit supported asset classes | Missing | Same |
| Explicit insufficient-data behavior | Missing/silent | Indicator functions return `None` under min length; lambdas null-check and simply return False — the user cannot distinguish "condition false" from "not computable on this timeframe" |

### 12.3 Hardcoded branches and assumptions found

- Asset-class branch in orchestration: exactly one — `symbols = CRYPTO_SYMBOLS if market == "crypto" else _stock_scan_symbols()` (`scans.py:336`).
- Timeframe-specific assumptions inside strategies: chart-pattern windows (60/20/30 bars) and "200-day SMA" naming assume daily-scale bars; the same bar counts are applied to 1-minute or 1-year bars unchanged (`technical.py:669-714`, filter description "Current price above 200-day SMA", `scans.py:140`).
- Duplicate indicator logic: signal thresholds appear twice — once in `full_analysis` signal counting (`technical.py:762-799`) and again as filter lambdas (`scans.py:126-151`); a third partial copy exists in the frontend's indicator cards (`StockDetailModal.jsx:205-233`) and legend/series computation in `CandlestickChart.jsx` (frontend recomputes EMAs from chart data for display, `CandlestickChart.jsx:15-20,95-102`).
- Frontend/backend strategy mismatch: none in the stocks direction (the FilterPanel is fully data-driven from `/api/filters`, `FilterPanel.jsx:152-203`, so any new backend filter appears automatically — a genuine strength). In the reverse direction, backend-detected bearish chart patterns are not selectable (D-7).

### 12.4 Eager computation

`full_analysis` computes **all** indicators, Fibonacci analysis, both pattern families, and a full trade setup for every symbol on every scan regardless of the selected filters (`technical.py:732-746,828-832`). With ~800 universe symbols this is CPU waste and, more importantly for architecture, prevents any strategy from declaring what it needs.

### 12.5 Conclusion

A new *filter* can be added by editing only `FILTER_DEFINITIONS` (orchestration control flow is generic), so the letter of "add a strategy without touching orchestration code" is nearly met — but only because everything lives in one module; the file being edited *is* the orchestration file, definitions cannot carry parameters/capabilities, and any strategy needing a new computed input must also modify `TechnicalAnalysis.full_analysis`. A new *strategy type* (e.g., YOLO-in-scan, cross-symbol momentum ranking, multi-timeframe confirmation) does not fit the `check(analysis)` shape at all and would require orchestration changes.

### 12.6 Strategy execution trace (required)

```text
User checks "MACD Bullish"                    FilterPanel.jsx:175-198 (key 'macd_bullish' from /api/filters payload)
→ selectedFilters state                       useMarketStore.js:73-80
→ POST /api/scan filters:['macd_bullish']     useMarketStore.js:156-161
→ ScanRequest.filters validated (1–25 items)  schemas/market.py:17
→ scan_market: valid_filters intersection     scans.py:337-340 (unknown keys silently dropped; all-unknown → 400)
→ per symbol: ta.full_analysis(bars)          scans.py:423
→ MACD computed: EMA12−EMA26, signal EMA9     technical.py:46-55 (needs ≥35 closes else (None,None,None))
→ lambda check: line > signal (null-guarded)  scans.py:142-143
→ matched_filters / match_pct                 scans.py:441-480
→ result row rsi+macd persisted               scans.py:503-508
→ UI: match bar + RSI cell + signal badge     ScanResults.jsx:157-175
```

---

## 13. Universe Architecture Assessment

### 13.1 Current model

- Schema: `UniverseSymbol(symbol, exchange, avg_daily_volume, rank, computed_at)` with `CheckConstraint("exchange IN ('NASDAQ','NYSE')")` and per-exchange rank uniqueness (`backend/models/universe.py:6-19`).
- Build: reference tickers per exchange (`XNAS`/`XNYS`, `type=CS`, paginated — `universe_builder.py:54-74`, `polygon.py:255-274`) → grouped daily US-stocks bars for each day in a 730-day lookback, fetched concurrently (`universe_builder.py:85-137`) → average daily volume → per-exchange rank → top 500/300 → transactional delete-and-insert (`universe_builder.py:140-181`).
- Consumption: `get_scan_universe_symbols(fallback)` returns **all** rows ordered by exchange+rank, or the 80-symbol fallback on empty/error (`universe_builder.py:215-235`); scan-side entry is `_stock_scan_symbols()` (`scans.py:64-67`).
- Ops: CLI `rebuild-universe`, `GET /api/universe/status` (counts + computed_at only), optional RQ-scheduled refresh (`universe_builder.py:238-303`).
- Frontend: no universe selection of any kind; the FilterPanel footnote says only "Uses the current backend scan universe" (`FilterPanel.jsx:225-227`).

### 13.2 Equity assumptions vs crypto requirements

| Dimension | Current equity assumption | Crypto reality it cannot express |
|---|---|---|
| Identity | One symbol per listing, keyed by exchange | Trading **pair** (base+quote) per venue; BTC exists as X:BTCUSD, X:BTCEUR, … |
| Eligibility | `type=CS` common stock on XNAS/XNYS | Quote-currency filter (USD/USDT/stablecoin), venue coverage, instrument availability |
| Ranking metric | Share-count average daily volume from grouped **stocks** endpoint (`polygon.py:276-282` is `/market/stocks/` only) | Notional/24 h volume, market cap, liquidity; share-count volume is meaningless across price scales |
| Calendar | Trading-day gaps skipped as weekends/holidays (`universe_builder.py:104-111`) | 24/7 — every calendar day should have data; a missing day is an error signal, not a weekend |
| Lookback | 730 daily bars | Younger assets may have short histories; two-year averages bias against new listings |
| Storage | `exchange` CHECK constraint blocks any non-NASDAQ/NYSE row | Needs venue/asset-class columns or a per-class table |
| Scan scoping | Whole table, both exchanges merged | Needs per-universe selection (also missing for equities) |

### 13.3 Conclusion

The universe architecture is **structurally equity-specific** — not superficially generic. Extending it to crypto requires schema change (the CHECK constraint), a second provider path (grouped-daily is stocks-only; the crypto snapshot endpoint `polygon.py:284-289` returns current-day snapshots, not history), a different ranking policy, and a scan-request universe parameter that does not exist today. The equities side also lacks exchange-scoped scanning even though the data model already stores exchange.

---

## 14. End-to-End Timeframe Assessment

### 14.1 Propagation trace (required)

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
14. Deterministic pattern detection: fixed bar windows                      technical.py:614-714
15. YOLOv8: timeframe passed only as metadata for TA confirmation + logs    pattern_detection.py:64-74; CandlestickChart.jsx:313-317
16. Signal resolution: timeframe-independent                                signalResolver.py
17. Result schema: meta.timeframe + per-row persistence                     scans.py:658; models/scan.py:22 (CHECK constraint from TIMEFRAME_CHECK_SQL, market_config.py:146-148)
18. Result storage: ScanResult/ScanHistory rows                             scans.py:492-513,629-641
19. Frontend display: meta.timeframe chip; detail modal selector            ScanResults.jsx:113; StockDetailModal.jsx:85-129 (changeDetailTimeframe re-fetches, useMarketStore.js:239-261)
20. Chart rendering: epoch-ms → epoch-s, sorted                             CandlestickChart.jsx:68-88
```

**Determination:** timeframe is a **first-class domain parameter throughout**; no point loses, replaces, defaults, or misinterprets it. Both asset classes take the identical path.

### 14.2 Weaknesses (all Partial rather than broken)

1. **Fixed lookback windows** (`days` per timeframe, `market_config.py`) rather than computed "N bars needed × interval" lookbacks. On `1Y` the window is 12,775 days but most listings yield far fewer than the 30 bars `full_analysis` requires, so `1Y` scans will reject most symbols as insufficient; on `1m` the 5-day window is at the mercy of the Polygon plan's intraday history (`data_limit_notice`, `market_config.py:164-171`, surfaces this to the UI — `ScanResults.jsx:93-98`).
2. **`min_bars` is decorative for scans**: it feeds only the intraday notice; the actual gate is the hardcoded 30 in `scans.py:404` and `technical.py:719`.
3. **Long-lookback silent degradation**: EMA/SMA-200 and 60-bar chart patterns silently return `None`/empty on short histories, so on `1M`/`1Y` the filters `ema_golden_cross`, `ema_death_cross`, `price_above_sma200`, `chart_pattern_bullish` can never match and the user is never told (F-004).
4. **No local aggregation**: any interval Polygon's plan rejects simply produces zero bars → `provider_data_unavailable` (`scans.py:610-627`); there is no resample-from-lower-interval fallback. Whether specific plans reject `45m` or intraday history depths: `Requires external provider verification`.
5. **Session/calendar model absent**: incomplete trailing candles are not trimmed (today's partial bar participates in "last price" and patterns); time zones/DST are delegated wholly to Polygon bar timestamps; equity RTH vs crypto 24/7 differences are unmodeled.

### 14.3 Timeframe support matrix (required)

Legend: S = Supported, P = Partial, U = Unsupported, V = Unverified. Columns: FE = frontend selection, API = API validation, ORCH = scan orchestration, STK = stock provider support, CRY = crypto provider support, RET = candle retrieval, AGG = local aggregation/resampling, IND = indicator computation, STRAT = strategy execution, TAP = deterministic (TA-style) pattern detection, YOLO = YOLOv8 detection, RES = result generation, CHART = charting.

| TF | FE | API | ORCH | STK | CRY | RET | AGG | IND | STRAT | TAP | YOLO | RES | CHART |
|----|----|-----|------|-----|-----|-----|-----|-----|-------|-----|------|-----|-------|
| 1m | S | S | S | P | V | S | U | P | P | P | V | S | S |
| 5m | S | S | S | P | V | S | U | P | P | P | V | S | S |
| 15m | S | S | S | P | V | S | U | P | P | P | V | S | S |
| 30m | S | S | S | P | V | S | U | P | P | P | V | S | S |
| 45m | S | S | S | V | V | S | U | P | P | P | V | S | S |
| 1H | S | S | S | P | V | S | U | S | S | S | V | S | S |
| 4H | S | S | S | P | V | S | U | S | S | S | V | S | S |
| 1D | S | S | S | S | V | S | U | S | S | S | V | S | S |
| 1W | S | S | S | S | V | S | U | S | S | S | V | S | S |
| 1M | S | S | S | S | V | S | U | P | P | P | V | S | S |
| 1Y | S | S | S | V | V | S | U | P | P | P | V | S | S |

Explanations for every non-`Supported` cell:

- **STK = P (1m–30m, 1H, 4H):** intraday history depth is plan-dependent; the code anticipates this via `data_limit_notice` (`market_config.py:164-171`) and the tests assert the notice fires at 60 bars (`test_scans_provider_errors.py:142-144`). Exact plan limits: `Requires external provider verification`.
- **STK = V (45m):** 45-minute is a non-standard multiplier; Polygon aggregates accept arbitrary multipliers per the client construction (`polygon.py:218`), but no test or log evidence in the repo demonstrates real 45m responses. `Requires external provider verification`.
- **STK = V (1Y):** `timespan=year` is requested (`market_config.py:127-137`) but nothing in the repo evidences real yearly-bar responses at 30+ bars. `Requires external provider verification`.
- **CRY = V (all):** the code path is identical, and the conftest mock covers it generically, but no test, fixture, or log in the repo shows real Polygon **crypto** aggregates for any span; plan gating differs between stock and crypto products. `Requires external provider verification`.
- **AGG = U (all):** no resampling/aggregation code exists in the backend; every interval must be provider-native (design gap, listed as F-008).
- **IND/STRAT/TAP = P (1m–45m):** computable, but window/threshold constants are daily-calibrated (e.g., "200-day SMA" naming `scans.py:140`; 3 % double-bottom tolerance `technical.py:682`), and plan-limited intraday history frequently leaves <200 bars so EMA/SMA-200 filters silently degrade.
- **IND/STRAT/TAP = P (1M, 1Y):** 30-bar full-analysis floor and 60-bar chart-pattern window mean months (~30 bars ≈ 2.5 years of data needed → OK for old listings, missing for young ones) and years (30 yearly bars ≈ 30-year listings) mostly cannot compute long-lookback indicators or chart patterns; failures are silent (F-004).
- **YOLO = V (all):** YOLOv8 runs on whatever chart image the browser captures at any timeframe; the model card is for stock chart patterns and no per-timeframe validation exists in the repo (Section 17).

---

## 15. (Matrix consolidated into Section 14.3)

The required timeframe support matrix appears in Section 14.3 above.

---

## 16. End-to-End User Capability Matrix

Steps per the brief: (1) reach scan UI, (2) select asset class, (3) select market/universe/symbol/pair, (4) select timeframe, (5) select strategies, (6) start scan, (7) receive response, (8) interpret bullish/bearish/neutral/insufficient-data, (9) view chart+indicators.

| Step | NASDAQ | NYSE | Cryptocurrency |
|---|---|---|---|
| 1. Reach scan interface | Complete (`/` route, `App.jsx:183`) | Complete | Complete |
| 2. Select asset class | Complete (toggle = "Stocks") | Complete | Complete (toggle = "Crypto", `Header.jsx:66-80`) |
| 3. Select market/universe/symbol/pair | **Missing** — NASDAQ cannot be selected separately from NYSE; scans always run over the merged universe (`universe_builder.py:215-235`); no symbol-scoped scan | **Missing** (same) | **Missing** — no pair/venue/universe choice; fixed 15 pairs (`scans.py:36-40`) |
| 4. Select timeframe | Complete (`FilterPanel.jsx:74-92`) | Complete | Complete |
| 5. Select strategies | Complete (data-driven checkboxes/presets) | Complete | Complete — but with no indication of crypto validity |
| 6. Start scan | Complete (requires sign-in: `@token_required`, `scan_routes.py:51`) | Complete | Complete |
| 7. Receive valid response | Complete (async job + polling) | Complete | Complete |
| 8. Interpret bullish/bearish/neutral/insufficient-data | Partial — bullish/bearish/neutral badges complete (`ScanResults.jsx:73-82`); insufficient-data is only an aggregate counter in meta/logs, never surfaced per symbol; long-lookback filter degradation invisible | Partial (same) | Partial (same) |
| 9. View chart and indicators | Complete (`StockDetailModal.jsx`, `CandlestickChart.jsx`) | Complete | Complete (X:-symbols render; volume/price semantics unlabeled for pairs) |
| **Overall** | **Partial** | **Partial** | **Partial** |

No asset class earns `Complete` overall: equities lack exchange/universe/symbol scoping and per-symbol insufficient-data interpretation; crypto additionally lacks any universe beyond 15 fixed pairs.

---

## 17. Pattern Detection and YOLOv8 Assessment

### Current implementation

- Deterministic detection (`technical.py:614-714`): 7 candlestick + 5 chart patterns; runs inside every scan and in `full_analysis`; drives the `bullish_pattern`/`bearish_pattern`/`chart_pattern_bullish` filters. Never uses YOLO (asserted: `test_scans_provider_errors.py:88-106`).
- YOLOv8 (`yoloService.py`): singleton, model auto-downloaded from `https://huggingface.co/foduucom/stockmarket-pattern-detection-yolov8` (`yoloService.py:13`), 0.50 confidence threshold, browser-captured chart images only (`pattern_detection.py:52-108`), authenticated + Redis rate-limited endpoint (`pattern_routes.py:12-23`, `pattern_detection.py:188-207`).
- Resolution (`signalResolver.py:15-52`): YOLO detections above threshold become candidates; internal-TA agreement upgrades priority to 1 and badge to "YOLOv8 + TA-Lib"; disagreement sets `talib_conflict`; below-threshold YOLO yields the empty signal — internal TA alone never produces a primary signal.
- Frontend: "Detect Patterns" button on any chart, overlay boxes scaled from capture size, conflict warning, disclaimer (`CandlestickChart.jsx:302-332,125-172`; badge/behavior confirmed against store/docs).

### Assessment against the brief

| Concern | Finding |
|---|---|
| Training-domain mismatch | The model card is stock-chart patterns. Crypto charts share candlestick grammar but differ in volatility distribution, session continuity, and the rendered chart's volume/indicator furniture. **No evidence of crypto validation exists in the repo.** Generalization must not be assumed. |
| Asset-class capability declaration | **Missing** — `PatternDetectRequest` (`schemas/patterns.py:9-37`) accepts any symbol; no market check anywhere in `pattern_detection.py` |
| Chart-rendering consistency | Detection input is whatever the user's theme/size/indicator-visibility state renders (`captureVisibleChart`, used at `CandlestickChart.jsx:312`); indicator overlays (EMA lines, Bollinger, MACD/RSI panes) are part of the captured image — a distribution the model was likely not trained on. Applies to both asset classes |
| Timeframe sensitivity | Timeframe is metadata only; the model sees pixels. No per-timeframe thresholds or validation |
| Confidence/false-positive controls | Single global threshold (0.50) via env; no per-class, per-asset, or per-timeframe calibration |
| TA/YOLO separation | Good: sources are kept distinct through `source_badge`, `talib_confirmation`, `talib_conflict`, and raw `yolo_results` + `talib_patterns` in the response (`pattern_detection.py:76-83`) |
| Disagreement behavior | Conflict is flagged, not suppressed — YOLO still wins with priority 2 (`signalResolver.py:27-39`) |
| Frontend presentation | Badge + confidence + conflict icon + persistent disclaimer — adequate, except the "TA-Lib" misnomer (D-2) |

### Recommendation (tied to findings F-007)

- **Near-term role:** keep YOLOv8 as an on-demand, single-chart research aid for **equities**; gate `POST /api/patterns/detect` on asset class and return an explicit "not validated for crypto" error (or a degraded TA-only response) when the symbol's market is crypto.
- **Conditions before enabling for crypto:** a labeled crypto-chart evaluation set rendered by this application's own chart pipeline (same theme/indicators), measured precision at the deployed threshold, per-class thresholds, and a documented pass criterion.
- **Long-term role:** one detector behind a capability-declaring detector interface alongside deterministic detection, with per-asset-class enablement flags and server-side chart rendering (or a canonicalized capture spec) to stabilize the input distribution.

---

## 18. Market-Data Provider Gaps (Massive/Polygon)

Assessed strictly from repository evidence; items the repo cannot prove are marked.

| Dimension | Stocks | Crypto | Evidence / verification status |
|---|---|---|---|
| Aggregates endpoint | `/v2/aggs/ticker/{T}/range/…` | Same endpoint, `X:`-prefixed ticker | `polygon.py:208-222` |
| Symbol format | Plain ticker | `X:BASEQUOTE` composed by `canonicalize_symbol` (USD hardcoded) | `symbols.py:24-41` |
| Reference/universe data | `/v3/reference/tickers?market=stocks&exchange=…` + grouped daily `/v2/aggs/grouped/locale/us/market/stocks/{date}` | Reference search `market=crypto` only; **no grouped-daily equivalent used**; snapshot `/v2/snapshot/locale/global/markets/crypto/tickers` exists but only for the optional prefilter | `polygon.py:255-289,298-309` |
| Supported intervals & history depth | All 11 canonical mappings are requested; intraday depth plan-limited (handled via notice) | Same mappings requested | `market_config.py`; depth/plan behavior: `Requires external provider verification` |
| Pagination | Reference tickers follow `next_url` fully | n/a for aggregates (limit=50000 single page assumed) | `polygon.py:258-274`; aggregate result truncation beyond 50k rows: `Requires external provider verification` |
| Rate limits / retry | 429 honors `Retry-After`, exponential backoff ×3, circuit breaker 5-failures/60 s, semaphore (default 10) | Shared | `polygon.py:17-24,125-171` |
| Caching | All GETs cached via `services/cache.py` (Redis w/ in-memory fallback); scan detail cached 120 s | Shared | `polygon.py:104-108,149`; `scans.py:276-302` |
| Corporate actions | `adjusted=true` on aggregates; dividends endpoint for fundamentals | Meaningless for crypto but harmless | `polygon.py:219,345-356` |
| Sessions / trading calendar | Implicit: grouped-day skips logged as weekend/holiday; no calendar model | 24/7 unmodeled | `universe_builder.py:104-111` |
| Volume semantics | Share volume; universe ranks by it | Polygon crypto `v` is base-asset volume; ranking by it across pairs is not meaningful — **no crypto ranking exists to misuse it yet** | `universe_builder.py:114-127` |
| Missing candles / gaps | Skipped days tolerated; no gap detection in scan bars | Same | `universe_builder.py:104-111`; no gap logic in `scans.py` |
| Real-time vs delayed | Not addressed; scans use end-of-window aggregates | Same | — ; plan latency: `Requires external provider verification` |
| Error handling surfaced to UI | `provider_not_configured` (503), `provider_data_unavailable` (502 with counters), data-limit notices | Shared | `scans.py:329-334,610-627`; `ScanResults.jsx:17-25,93-98` |
| Frontend-visible limitations | Plan-based timeframe disabling designed but non-functional (D-1); footer counts stale (D-4/F-011) | Same | `market_config.py:174-182`; `App.jsx:219` |

**Material gap summary:** the provider layer is a well-hardened transport but a single concrete class with implicit asset-class routing; there is no interface seam for a second provider, and the crypto side has no historical-universe data source (grouped-daily is stocks-only), which is the main provider-level obstacle to a real crypto universe.

---

## 19. Key Architectural Risks and Technical Debt

| ID | Finding (stable IDs referenced by the improvement plan) | Severity |
|----|---|---|
| F-001 | Crypto universe is a 15-symbol constant; no crypto universe construction anywhere (`scans.py:36-40`; builder/model equity-only) | Critical (product goal) |
| F-002 | Frontend crypto scan entry point **exists** but is a bare toggle: no venue/pair/universe context, no disclosure of the 15-pair limit, market-switch can mislabel stale results (`Header.jsx:66-80`; `ScanResults.jsx:48`) | Medium |
| F-003 | Strategies are inline lambdas co-located with orchestration; no contract, registry module, parameters, or versioning (`scans.py:124-179`) | High |
| F-004 | No per-strategy history/timeframe/asset declarations; long-lookback indicators silently `None` → filters silently unmatchable on 1M/1Y and plan-limited intraday (`scans.py:404`; `technical.py:12-23,669-672`) | High |
| F-005 | No capability metadata surface: `/api/filters` carries no per-market/per-timeframe validity; documented `available` flag never emitted (D-1) (`scans.py:237-251`; `market_config.py:174-182`) | High |
| F-006 | Universe schema and builder structurally equity-only (`models/universe.py:9`; `universe_builder.py:21-24`); no exchange/universe scoping in scan requests (`schemas/market.py:14-18`) | High |
| F-007 | YOLOv8 stock-trained model ungated by asset class; capture distribution uncontrolled; "TA-Lib" badge misnomer (`yoloService.py:13`; `pattern_detection.py:52-83`; `signalResolver.py:35`) | Medium |
| F-008 | Timeframe lookbacks fixed in calendar days; single global 30-bar gate; `min_bars` unused for gating; no aggregation fallback; no session/incomplete-candle model (`market_config.py`; `scans.py:404`) | Medium |
| F-009 | Direct `polygon` singleton coupling in scans/universe/fundamentals/news; no provider interface; asset routing implicit in ticker prefix (`clients/polygon.py:359`; imports in `scans.py:7`, `universe_builder.py:12`) | Medium |
| F-010 | Zero automated coverage of the crypto scan path (backend grep evidence; frontend tests touch crypto only via a template payload, `useMarketStore.test.js:116-138`) | High |
| F-011 | Health payload/footer report fixed fallback counts, not real universe (`scans.py:227-234`; `App.jsx:219`) | Low |
| F-012 | `full_analysis` computes everything for every symbol regardless of selected filters; scan loop is sequential per symbol (`technical.py:716-853`; `scans.py:381`) | Medium |
| F-013 | Documentation drift items D-1, D-2, D-5, D-7 | Low |
| F-014 | Symbol model lacks pair semantics: `canonicalize_symbol` hardcodes USD quote; no base/quote/venue fields anywhere (`symbols.py:24-41`) | Medium |
| F-015 | Insufficient-data results invisible per symbol/strategy to users (aggregate counters only, `scans.py:654-681`) | Medium |

---

## 20. Target Architecture

Facts above are current state; everything in this section is proposal. The design deliberately preserves: the async RQ job flow, the canonical timeframe map, the pydantic validation layer, the data-driven FilterPanel, the hardened Polygon transport, and the analysis-dict decoupling of filters.

### 20.1 Asset-class abstraction

Introduce a small domain layer (new `backend/domain/` package) instead of today's `CanonicalSymbol` triple:

- `AssetClass` enum: `EQUITY`, `CRYPTO` (string-compatible with the existing `stocks`/`crypto` wire values to avoid breaking `ScanRequest` and DB CHECKs).
- `Instrument`: `symbol` (display), `provider_symbol`, `asset_class`, `venue` (e.g., `XNAS`, `XNYS`, `GLOBAL_CRYPTO`), and for crypto `base_currency`/`quote_currency`. This replaces the USD-hardcoding heuristic in `symbols.py:24-41` with explicit pair construction, while keeping `canonicalize_symbol` as a compatibility shim.
- `MarketCapabilities` (per asset class, served by the API): supported timeframes (with plan-derived `available` finally emitted, closing D-1), supported strategies, session model (`RTH` vs `24/7`), and detector availability (YOLO on/off).
- `MarketDataRequest`: `(instrument, timeframe, min_bars_required)` — lets the fetch layer compute lookback from bar needs instead of fixed `days` (fixes half of F-008).
- `Candle`: keep the existing `{t,o,h,l,c,v}` dict shape (it already crosses backend/frontend cleanly); document volume semantics per asset class in instrument metadata rather than normalizing them away.

Normalize: OHLCV structure, timeframe identity, signal vocabulary (bullish/bearish/neutral/insufficient_data). Keep explicit: venue, quote currency, session model, volume semantics, provider symbol mapping. Invalid combinations (e.g., strategy not supporting `1Y`, YOLO on crypto) are rejected at request validation using the same capability registry the frontend reads — one source of truth, enforced server-side.

### 20.2 Strategy and filter model

Replace the lambda dict with a declarative strategy contract in a new `backend/strategies/` package, keeping the existing filter keys as strategy IDs so saved templates and frontend state remain valid:

```python
class Strategy(Protocol):
    id: str; version: str; name: str; description: str; category: str
    params_schema: type[BaseModel]          # pydantic; empty model for legacy filters
    required_history: int                    # bars, e.g. 200 for ema_golden_cross
    required_features: set[str]              # {'rsi'}, {'ema','fibonacci'}, ...
    supported_asset_classes: set[AssetClass] # default: both
    supported_timeframes: set[str] | None    # None = all canonical
    def evaluate(self, ctx: StrategyContext) -> StrategyResult  # signal, score, explanation, evidence
```

`StrategyResult.signal ∈ {bullish, bearish, neutral, insufficient_data}` makes the currently-silent degradation (F-004) explicit. A module-level registry (`register(strategy)` at import time, discovered via package scan) replaces `FILTER_DEFINITIONS`; `scan_market` iterates the registry and never changes when strategies are added (fixes F-003). `required_features` drives selective computation in `TechnicalAnalysis` (fixes F-012's eager-compute half). `filters_payload()` is generated from the registry including capability metadata (fixes F-005). Dependency injection stays lightweight: strategies receive a context object (bars, computed features, instrument, timeframe) — no provider access, preserving today's best property.

### 20.3 Generalized universe model

- Contract: `UniverseProvider.build() -> list[UniverseEntry]` and `UniverseProvider.symbols(universe_key) -> list[Instrument]`, with `universe_key` ∈ {`nasdaq_top`, `nyse_top`, `us_stocks_top` (merged, current behavior), `crypto_usd_top`, later `watchlist:<id>`}.
- Storage: widen `universe_symbols` — replace the NASDAQ/NYSE CHECK with (`asset_class`, `venue`, `quote_currency?`) columns and per-universe rank uniqueness; migration keeps existing rows as `asset_class='equity'`.
- Equity policy: current volume ranking unchanged.
- Crypto policy: rank by notional volume/market presence from the crypto snapshot endpoint accumulated over time, or 24 h notional volume × liquidity floor, restricted to a configurable quote currency (default USD); shorter lookback; every-day-expected calendar. Repo evidence cannot confirm which crypto ranking inputs the plan provides — flagged as a provider-validation task in the plan.
- Scan request gains an optional `universe` field (default preserves today's behavior per market), giving equities the missing NASDAQ/NYSE scoping using data the table already stores.

### 20.4 End-to-end timeframe model

- Canonical representation stays the `market_config.py` string keys (proven end-to-end).
- Provider mapping stays at the client boundary (multiplier/timespan) — the only place provider notation may appear.
- Lookback becomes computed: `lookback = required_bars × interval × session_factor(asset_class)` with per-class calendars (equity RTH vs crypto 24/7), replacing fixed `days`.
- `min_bars` becomes enforced input to scan gating and per-strategy `required_history` checks; insufficient data becomes a first-class per-symbol result rather than a skip counter (fixes F-015).
- Aggregation: add a single optional resampling step (pandas resample on provider bars) used only when a canonical interval is plan-unavailable (e.g., build 45m from 15m); calendar intervals (1M/1Y) remain provider-native. Incomplete trailing candles get a `partial` flag and are excluded from pattern windows by default.

### 20.5 Frontend asset-class and market surface

- Keep the header toggle as the asset-class selector; add beneath the FilterPanel timeframe row a **universe selector** (populated from `GET /api/capabilities`): equities → All US / NASDAQ / NYSE; crypto → Top USD pairs (with its size shown, removing the silent-15 problem).
- Capability-driven disabling: timeframe buttons and strategy checkboxes read the capability payload; unsupported combinations render disabled with the reason as tooltip — the components already implement the disabled pattern for timeframes (`FilterPanel.jsx:79-92`), so this is wiring, not new UI machinery.
- On market switch: clear or visibly mark stale results (`scanResults` tagged with the market they came from), fixing the F-002 mislabel case; preserve per-market filter/timeframe selections in the store.
- Result labeling: keep per-row market badges; add per-symbol `insufficient_data` rows/notices sourced from the new StrategyResult signal.
- No business rules hardcoded client-side: the frontend renders whatever `capabilities` returns.

### 20.6 YOLOv8 capability controls

Per Section 17: declare YOLO as an equity-only detector in `MarketCapabilities`; enforce server-side in `pattern_routes`/`pattern_detection`; hide/disable the Detect Patterns button for crypto charts from the same capability payload; rename the badge to reflect the real confirmation source; define a crypto validation protocol before ever flipping the capability flag.

### 20.7 Provider abstraction

Extract a `MarketDataProvider` Protocol (`get_bars(instrument, timeframe, lookback)`, `search(query, asset_class)`, `reference_universe(asset_class, venue)`, `snapshot(asset_class)`) implemented by the existing `PolygonClient` internals. Consumers (`scans`, `universe`, `pattern_detection`) depend on the protocol; the singleton remains the default binding. This is a seam, not a rewrite — transport hardening code is untouched.

---

## 21. Recommended Architectural Decisions

1. **ADR-1: Keep `stocks`/`crypto` wire values and filter keys stable** while introducing the domain layer — protects DB CHECK constraints, saved templates (`scan_templates.criteria_json`), and localStorage/frontend state. (Addresses migration risk in F-001/F-003.)
2. **ADR-2: Capability metadata is server-owned and dual-purpose** — the same registry validates requests and feeds the UI (`/api/capabilities` or extended `/api/filters`). Never let the frontend infer validity. (F-005, D-1.)
3. **ADR-3: Strategy registry with declared requirements** replaces `FILTER_DEFINITIONS`; `insufficient_data` becomes a first-class signal. (F-003, F-004, F-015.)
4. **ADR-4: Universe as pluggable providers over a widened table**, with request-level universe selection. (F-001, F-006.)
5. **ADR-5: Computed lookbacks + enforced `min_bars` + optional resampling**, with per-asset-class session calendars. (F-008.)
6. **ADR-6: YOLO gated equity-only until a documented crypto validation passes.** (F-007.)
7. **ADR-7: Provider Protocol seam around the existing client**; no second provider until the seam exists. (F-009.)
8. **ADR-8: Characterization tests before refactoring** — especially a crypto scan test, currently absent. (F-010.)

---

## 22. Open Questions Requiring External or Product Confirmation

1. **Polygon plan coverage** (`Requires external provider verification`): intraday history depth per span; whether `45m` and `year` aggregates return usable data; crypto aggregates entitlement and history depth; crypto snapshot fields available for ranking (notional volume? market cap is likely absent); real-time vs delayed entitlements.
2. **Product**: Should equities be scannable per exchange (the data supports it) — and is the merged behavior intentional? What is the desired crypto universe policy (top-N by what metric, which quote currencies, which venues)? Should scans be scoped to a watchlist/symbol set? Is `1Y` scanning a real use case given ~30-bar requirements imply 30-year listings?
3. **Product/ML**: Is YOLOv8 intended for crypto at all? If yes, who owns building the labeled evaluation set?
4. **Ops**: Is the plan-based timeframe `available` flag (D-1) still wanted, and what should populate it?

---

## 23. Review Limitations

- Read-only static review; no server, worker, or scans were executed, and no live Polygon calls were made. All "works end-to-end" claims are code-trace conclusions corroborated by existing automated tests, not fresh runtime observation.
- `CandlestickChart.jsx` lines ~370–899 (series builders/legend plumbing) were skimmed via targeted greps, not read line-by-line; conclusions about chart timeframe handling rest on the read portion (lines 1–370).
- `backend/factory.py` lines 120–300 (error handlers, headers, YOLO startup, scheduler wiring) were not read in full; doc claims about them were spot-checked only where they intersect scan paths.
- Frontend unit tests other than `useMarketStore.test.js` (FilterPanel, StockDetailModal, Watchlist, Admin tests) were not read; their existence is taken from the file tree.
- News/fundamentals services were assessed only at their provider imports; auth/admin modules were deliberately not reviewed (scope exclusion).
- Provider-plan behavior is unverifiable from the repository and is marked accordingly throughout.

---

## 24. Review Coverage Table

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
