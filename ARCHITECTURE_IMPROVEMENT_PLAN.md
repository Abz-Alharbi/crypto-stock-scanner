# Architecture Improvement Plan — Market Scanner Pro

Companion to `ARCHITECTURE_REVIEW.md` (2026-07-11). All finding IDs (F-001…F-015) and discrepancy IDs (D-1…D-7) refer to that review. This plan contains no authentication, authorization, account, or administration work.

---

## 1. Improvement Principles

1. **Refactor under characterization tests.** The crypto scan path has zero test coverage today (F-010); nothing structural moves until the current behavior is pinned.
2. **Keep the wire contract and persistence stable.** `market ∈ {stocks, crypto}`, canonical timeframe strings, existing filter keys, and DB CHECK constraints (`backend/models/scan.py:10-13`) stay valid throughout; new fields are additive and optional.
3. **One source of truth for capabilities.** The same server-side registry that validates a request feeds the frontend; the UI never re-derives business rules (review §20.5, ADR-2).
4. **Preserve what already works.** The async RQ job flow, hardened Polygon transport (`backend/clients/polygon.py`), pydantic validation layer, data-driven FilterPanel, and the provider-decoupled analysis-dict pattern are kept, not rewritten.
5. **Seams before features.** Provider interface, strategy registry, and universe contract land before crypto enablement widens — broad crypto work on today's structure would multiply the one `market ==` branch into many.
6. **Silent degradation becomes explicit.** Every place where a computation silently returns `None` (F-004, F-015) becomes a declared `insufficient_data` outcome.
7. **No invented provider behavior.** Every plan step that depends on Polygon plan entitlements starts with a verification task (Section 10).

---

## 2. Findings-to-Phases Traceability Matrix

| Finding ID | Current gap | Evidence location in review | Target phase | Completion criterion |
|---|---|---|---|---|
| F-001 | Crypto universe is a hardcoded 15-pair constant; no crypto universe construction | §8, §11, §13 (`scans.py:36-40`) | P8 (foundation in P5) | A ranked crypto USD-pair universe is built, persisted, refreshable, and used by crypto scans; the constant remains only as fallback |
| F-002 | Crypto scan entry point exists but is a bare toggle; stale-result mislabeling; hidden 15-pair limit | §9, §11 (Header.jsx:66-80; ScanResults.jsx:48) | P7 | Universe size/name visible in scan UI; results tagged with their own market; switching markets never mislabels prior results |
| F-003 | Strategies are inline lambdas co-located with orchestration; no contract/registry | §12 (`scans.py:124-179`) | P4 | New strategy added by dropping a module in `backend/strategies/` with zero edits to orchestration; registry test proves it |
| F-004 | No per-strategy history/timeframe/asset declarations; silent long-lookback degradation | §12.2, §14.2 (`scans.py:404`; `technical.py:12-23`) | P4 + P6 | Each strategy declares `required_history`/timeframes/asset classes; unmet requirements yield `insufficient_data`, not silent False |
| F-005 | No capability metadata; documented `available` flag never emitted (D-1) | §9, §14.2, review D-1 (`market_config.py:174-182`) | P4 + P7 | `/api/capabilities` (or extended `/api/filters`) drives both request validation and UI enable/disable states |
| F-006 | Universe schema/builder structurally equity-only; no exchange/universe scoping in requests | §13 (`models/universe.py:9`; `schemas/market.py:14-18`) | P5 | Universe table is asset-class/venue aware; `ScanRequest.universe` selects NASDAQ/NYSE/merged/crypto universes |
| F-007 | Stock-trained YOLO ungated by asset class; capture distribution uncontrolled; "TA-Lib" badge misnomer (D-2) | §17 (`yoloService.py:13`; `signalResolver.py:35`) | P10 | Crypto detect requests rejected/disabled via capability flag; badge renamed; crypto enablement gated on documented validation |
| F-008 | Fixed calendar-day lookbacks; global 30-bar gate; `min_bars` decorative; no resampling; no session model | §14.2 (`market_config.py`; `scans.py:404`) | P6 | Lookback computed from required bars × session calendar; `min_bars` enforced; optional resample fallback for plan-unavailable intervals |
| F-009 | Direct `polygon` singleton coupling; no provider interface | §18, ADR-7 (`clients/polygon.py:359`) | P3 | Scans/universe/pattern services depend on a `MarketDataProvider` protocol; Polygon is one binding; a fake provider powers tests |
| F-010 | No automated crypto scan coverage | §8 item 4, §19 | P1 (chars.) + P9 (validation) | `scan_market('crypto', …)` covered in backend tests; frontend store test covers a crypto runScan; e2e includes market toggle |
| F-011 | Health/footer report fixed fallback counts | review D-4/F-011 (`scans.py:227-234`; `App.jsx:219`) | P1 | Health payload and footer show live universe counts per asset class |
| F-012 | Eager full analysis for every symbol; sequential scan loop | §12.4 (`technical.py:716-853`; `scans.py:381`) | P4 (selective compute) + P11 (concurrency) | Only features required by selected strategies are computed; measured scan wall-time reduction recorded |
| F-013 | Documentation drift (D-1, D-2, D-5, D-7) | §5 | P1 | `PROJECT_DOCUMENTATION.md` corrected or code aligned, item by item |
| F-014 | No pair semantics; USD quote hardcoded in `canonicalize_symbol` | §10, §20.1 (`symbols.py:24-41`) | P2 | `Instrument` carries base/quote/venue; canonicalization is a compatibility shim over it |
| F-015 | Per-symbol insufficient-data invisible to users | §16 step 8 (`scans.py:654-681`) | P6 + P7 | Scan responses include per-symbol insufficient-data entries; UI renders them distinctly |

Every critical/high finding (F-001, F-003, F-004, F-005, F-006, F-010) is covered by at least one phase; every phase below references at least one finding ID.

---

## 3. Phase Overview

| # | Phase | Primary findings | Depends on |
|---|---|---|---|
| P1 | Characterization tests & documentation reconciliation | F-010, F-011, F-013 | — |
| P2 | Canonical domain models (asset, instrument, candle, timeframe) | F-014, F-008 (types only) | P1 |
| P3 | Market-data provider abstraction | F-009 | P2 |
| P4 | Strategy contract, registry & capability metadata | F-003, F-004, F-005, F-012 | P2 |
| P5 | Generalized universe providers | F-006, F-001 (foundation) | P2, P3 |
| P6 | End-to-end timeframe correction | F-008, F-004, F-015 | P2, P4 |
| P7 | Frontend asset-class, universe & capability surface | F-002, F-005, F-015 | P4, P5 |
| P8 | Cryptocurrency data path & universe implementation | F-001 | P3, P5, P6 |
| P9 | Cross-asset strategy validation | F-010, F-004 | P4, P8 |
| P10 | Pattern-detection & YOLOv8 capability controls | F-007 | P4 (capability registry) |
| P11 | Observability, performance, caching, resilience | F-012, F-011 | P3–P8 |
| P12 | Final integration & acceptance testing | all | P1–P11 |

Sequencing rationale: P2–P5 establish the seams (domain, provider, strategy, universe) demanded by ADR-1/3/4/7 before crypto enablement (P8) broadens scope; P6/P7 can run partially in parallel with P5 once P4 lands.

---

## 4. Detailed Phased Implementation Plan

### Phase 1 — Characterization tests and documentation reconciliation

- **Goal:** pin current behavior; make the crypto path and universe counters observable before anything moves.
- **Current problem / evidence:** no test calls `scan_market('crypto', …)` (review §8 item 4); footer/health report constants (`scans.py:227-234`, `App.jsx:219`); doc items D-1, D-2, D-5, D-7.
- **Changes:**
  1. Backend characterization tests (pattern of `backend/tests/test_scans_provider_errors.py`, reusing `StaticBarsPolygonClient`): crypto scan happy path (15 symbols attempted, `market='crypto'` persisted, `X:` symbols in results); crypto + intraday timeframe; crypto scan with a long-lookback filter on short bars (pins today's silent-False behavior so P4/P6 can assert the change deliberately).
  2. Frontend: store test for `runScan` with `activeMarket:'crypto'` asserting payload; extend `frontend/e2e/user-flow.spec.js` mock flow with a market-toggle step.
  3. Fix `health_payload()` to include live universe counts (from `universe_builder.status_payload()`) alongside the fallback counts; update the footer to prefer them (`App.jsx:218-220`).
  4. Documentation edits in `PROJECT_DOCUMENTATION.md`: remove/implement `available` claim (D-1 — final resolution in P4), rename "TA-Lib" wording or annotate it (D-2 — final rename in P10), document the header market toggle (D-5), note the missing bearish chart-pattern filter (D-7).
- **Files:** `backend/tests/test_scans_crypto.py` (new), `frontend/src/store/useMarketStore.test.js`, `frontend/e2e/user-flow.spec.js`, `backend/services/scans.py` (health only), `frontend/src/App.jsx`, `PROJECT_DOCUMENTATION.md`.
- **Migration/compat:** none — additive tests plus one payload field.
- **Risks:** low; health payload consumers (footer, e2e mock at `user-flow.spec.js:61`) must tolerate the new fields.
- **Completion criteria / done:** CI green with new tests; crypto scan behavior pinned in three tests; footer shows real universe counts; the four doc discrepancies each resolved or explicitly ticketed to their owning phase.

### Phase 2 — Canonical domain models

- **Goal:** introduce `AssetClass`, `Instrument` (base/quote/venue), `MarketDataRequest`, and typed timeframe helpers without changing wire formats.
- **Current problem / evidence:** `CanonicalSymbol` triple with USD-hardcoded pair heuristic (`symbols.py:24-41`, F-014); asset context is a bare string threaded through calls.
- **Changes:** new `backend/domain/` package (`asset.py`, `instrument.py`, `timeframes.py` re-exporting `market_config`); `canonicalize_symbol` reimplemented as a shim returning `Instrument`-backed values; explicit `Instrument.for_crypto(base, quote='USD', venue='GLOBAL_CRYPTO')` constructor replacing the append-`USD` heuristic; unit tests for round-tripping every symbol form seen in the repo (`AAPL`, `X:BTCUSD`, bare `BTC` + market hint).
- **Files:** `backend/domain/*` (new), `backend/symbols.py` (shim), touch-points that read `.market` remain unchanged.
- **Migration/compat:** wire values `stocks`/`crypto` map 1:1 to `AssetClass`; no DB change.
- **Risks:** watchlist/scan persistence rely on `canonicalize_symbol` semantics — the shim must be behaviorally identical (guarded by P1 tests plus existing `test_integration_routes.py:38-50`).
- **Done:** all existing tests pass with the shim in place; new domain tests cover pair construction; no endpoint payload diff.

### Phase 3 — Market-data provider abstraction

- **Goal:** a `MarketDataProvider` protocol seam around the existing client (ADR-7).
- **Current problem / evidence:** module-level `polygon` singleton imported by `scans.py:7`, `universe_builder.py:12`, fundamentals/news (F-009); tests must monkeypatch module attributes (`test_scans_provider_errors.py:74`).
- **Changes:** define protocol (`get_bars(instrument, timeframe, lookback)`, `search`, `reference_universe`, `crypto_snapshot`, `grouped_daily_stocks`); implement `PolygonProvider` delegating to the current `PolygonClient` (transport code untouched); inject via a module factory (`get_provider()`) that scans/universe/pattern services call; convert conftest's `MockPolygonClient` into a first-class `FakeProvider` fixture.
- **Files:** `backend/providers/__init__.py` + `backend/providers/polygon_provider.py` (new), `backend/services/scans.py`, `backend/services/universe/universe_builder.py`, `backend/services/pattern_detection.py`, `backend/tests/conftest.py`.
- **Migration/compat:** `backend/clients/polygon.py` stays; `polygon` singleton kept for fundamentals/news until they migrate (they are outside the scan path and may migrate opportunistically).
- **Risks:** cache keys currently embed raw endpoints (`polygon.py:104`) — keep caching inside the client so keys don't churn.
- **Done:** scan and universe tests run against `FakeProvider` without monkeypatching module globals; `PolygonClient` diff is zero.

### Phase 4 — Strategy contract, registry, and capability metadata

- **Goal:** replace `FILTER_DEFINITIONS` lambdas with registered strategy objects that declare requirements; emit capability metadata.
- **Current problem / evidence:** F-003 (`scans.py:124-179` co-located with orchestration), F-004 (global 30-bar gate `scans.py:404`; EMA-200 silent `None` `technical.py:18-23`), F-005 (`filters_payload` has no capability info, `scans.py:237-251`; documented `available` flag never emitted, `market_config.py:174-182`), F-012 (eager `full_analysis`).
- **Changes:**
  1. `backend/strategies/` package: base `Strategy` dataclass/Protocol per review §20.2; one module per category porting all 22 filters **with identical IDs and boolean semantics** (each port asserts equivalence against the P1-pinned behavior); presets move alongside.
  2. Registry with import-time registration + duplicate-ID guard; `get_flat_filters()` reimplemented over the registry (keeps `scan_market` call sites working during transition).
  3. `StrategyResult` with `signal ∈ {matched, not_matched, insufficient_data}` (mapped to bullish/bearish at the result layer as today); `required_history` enforced per strategy — a symbol with 40 bars can still match RSI strategies while EMA-200 strategies report `insufficient_data` instead of silently False.
  4. Selective feature computation: `TechnicalAnalysis.full_analysis(bars, features=…)` computes only the union of `required_features` across selected strategies (trade setup/fibonacci only when needed by strategies or detail views; `stock_detail` keeps requesting everything).
  5. Capability payload: extend `/api/filters` (additive) with per-strategy `supported_asset_classes`, `supported_timeframes`, `required_history`, and finally emit the timeframe `available` flag (resolving D-1) from provider-plan config.
  6. Request validation: `ScanRequest` cross-checks filters against the registry for the requested market/timeframe and returns a structured validation error naming the invalid combination.
- **Files:** `backend/strategies/*` (new), `backend/services/scans.py` (orchestration consumes registry; FILTER_DEFINITIONS removed at the end), `backend/services/technical.py`, `backend/schemas/market.py`, `backend/tests/*` (per-strategy unit tests).
- **Migration/compat:** filter keys unchanged → saved `scan_templates.criteria_json` and frontend selections keep working; the silently-dropping-unknown-filters behavior (`scans.py:338`) is replaced by explicit validation — verify no stored template carries an unknown key first.
- **Risks:** behavioral drift during the port (mitigated by equivalence tests); `insufficient_data` changes result counts — flag behind a response field, not a match-semantics change.
- **Done:** a demo strategy added in a single new file appears in `/api/filters`, is selectable in the untouched FilterPanel, executes in scans, and no orchestration file changed (registry test asserts `scans.py` has no strategy imports); all 22 legacy filters pass equivalence tests.

### Phase 5 — Generalized universe providers

- **Goal:** asset-class/venue-aware universe storage and per-request universe selection.
- **Current problem / evidence:** F-006 (`models/universe.py:9` CHECK NASDAQ/NYSE; builder equity-only `universe_builder.py:21-24`); no `universe` request parameter (`schemas/market.py:14-18`); merged-exchange scanning only (`universe_builder.py:215-235`).
- **Changes:**
  1. Migration: add `asset_class` (default `equity`), `venue`, `quote_currency` (nullable), `universe_key` columns to `universe_symbols`; replace the exchange CHECK; re-scope rank uniqueness to `(universe_key, rank)`; backfill existing rows (`NASDAQ`→`equity/XNAS/nasdaq_top` etc.).
  2. `UniverseProvider` contract + `EquityVolumeUniverseProvider` port of the current builder (behavior-identical, verified against `test_universe_builder.py`); registry of universe keys: `us_stocks_top` (merged — default, preserves today's scans), `nasdaq_top`, `nyse_top`, `crypto_static` (the 15-pair constant, formalized as a provider so crypto scans stop reading a constant in `scans.py`).
  3. `ScanRequest.universe: Optional[str]`; `scan_market` resolves symbols via the universe registry; default per market keeps current behavior byte-for-byte.
  4. `GET /api/universe/status` extended to report per-universe counts and freshness.
- **Files:** `migrations/versions/*` (new), `backend/models/universe.py`, `backend/services/universe/*`, `backend/schemas/market.py`, `backend/services/scans.py:336` (branch replaced by registry lookup), tests.
- **Migration/compat:** delete/insert rebuild pattern (`universe_builder.py:174-181`) preserved; old rows backfilled; API additions optional.
- **Risks:** migration on the production Postgres table with the rebuild scheduler enabled — coordinate a rebuild after deploy; rank-uniqueness re-scoping must match the rebuild's write pattern.
- **Done:** scans accept `universe`; NASDAQ-only and NYSE-only scans work through the API; crypto scans read the static universe via the same contract; universe builder tests green on both old and new selection paths.

### Phase 6 — End-to-end timeframe correction

- **Goal:** computed lookbacks, enforced minimum bars, explicit insufficient-data, optional resampling, session calendars.
- **Current problem / evidence:** F-008 (fixed `days`, `market_config.py`; global 30-bar gate `scans.py:404`; `min_bars` only feeds a notice `market_config.py:164-171`); F-015 (per-symbol insufficiency invisible, aggregate counters only `scans.py:654-681`); daily-calibrated pattern windows (`technical.py:669-714`).
- **Changes:**
  1. `lookback_for(timeframe, required_bars, asset_class)` in the domain layer using per-class session factors (equity ≈ 6.5 trading hours/5-day weeks; crypto 24/7); `get_bars_with_meta` uses it, with the current `days` values retained as caps/fallbacks.
  2. Required bars = max(`min_bars` config, max of selected strategies' `required_history`) — replaces the hardcoded 30.
  3. Per-symbol outcome records: scan meta gains `insufficient_data_symbols: [{symbol, bars, required}]`; strategy-level `insufficient_data` (from P4) included per result row where relevant.
  4. Optional resampling: single utility (pandas `resample` on provider bars) used only for canonical intervals the plan cannot serve natively (candidate: `45m` from `15m`), gated per interval by provider-verification results (Section 10); calendar intervals (`1M`, `1Y`) stay provider-native.
  5. Incomplete trailing candle: mark the last bar `partial` when its interval hasn't closed (computed from timeframe + now, per asset-class calendar); pattern windows exclude partial bars by default; chart still renders them.
  6. Pattern-window review: parameterize `detect_chart_patterns(window=…)` per timeframe category rather than a fixed 60.
- **Files:** `backend/domain/timeframes.py`, `backend/services/scans.py`, `backend/services/technical.py`, `backend/market_config.py` (data only), tests including crypto-vs-equity lookback assertions.
- **Migration/compat:** meta fields additive; scan results may change where the 30-bar gate previously admitted symbols that long-lookback strategies couldn't evaluate — release-note this.
- **Risks:** larger lookbacks increase provider load for 200-bar strategies on `1D` (~200 trading days ≈ today's 730-day window already covers it — verify per timeframe); resampling correctness (bar alignment) needs golden-file tests.
- **Done:** timeframe matrix cells graded `Partial` in review §14.3 for IND/STRAT/TAP become either `Supported` (with explicit insufficient-data) or explicitly rejected combinations; tests demonstrate a `1M` scan reporting `insufficient_data` for EMA-200 strategies instead of silence.

### Phase 7 — Frontend asset-class, universe, and capability surface

- **Goal:** expose universe choice, capability-driven controls, truthful labeling.
- **Current problem / evidence:** F-002 (bare toggle; stale-result mislabeling `ScanResults.jsx:48`; hidden 15-pair limit), F-005 (no capability data consumed because none exists), F-015 (no insufficient-data rendering).
- **Changes:**
  1. Store: keep `activeMarket`; add `activeUniverse` (defaulted from capabilities per market); tag `scanResults`/`scanMeta` with the market+universe they came from; on `setMarket`, preserve per-market filter/timeframe selections and visually mark (not necessarily clear) results from the other market.
  2. FilterPanel: universe selector row (radio/select fed by capabilities, showing symbol counts — e.g., "Crypto · Top USD pairs (15)"); strategy checkboxes disable with tooltip when the capability payload marks them unsupported for the current market/timeframe (same disabled pattern already used for timeframes, `FilterPanel.jsx:79-92`).
  3. Timeframe buttons finally honor real `available` flags (D-1 resolved end-to-end).
  4. ScanResults: render `insufficient_data_symbols` in a collapsible notice; derive copy from `scanMeta.market` instead of `activeMarket` (fixes the §9 mislabel).
  5. Request construction includes `universe`.
- **Files:** `frontend/src/store/useMarketStore.js`, `frontend/src/components/filters/FilterPanel.jsx`, `frontend/src/components/stock/ScanResults.jsx`, `frontend/src/services/api.js`, component tests.
- **Migration/compat:** all new request fields optional; UI works against an old backend by treating missing capability data as "all allowed" (the current `available !== false` idiom).
- **Risks:** store shape changes ripple into `useMarketStore.test.js` and e2e mocks — update in the same PR.
- **Done:** a user can select NASDAQ-only, NYSE-only, merged, or crypto universes; unsupported strategy/timeframe combos are visibly disabled with reasons; switching markets never relabels existing results.

### Phase 8 — Cryptocurrency data path and universe implementation

- **Goal:** replace the 15-pair constant with a built, ranked, refreshable crypto universe (F-001).
- **Current problem / evidence:** `scans.py:36-40`; no crypto history source in the builder (grouped-daily is stocks-only, `polygon.py:276-282`); crypto snapshot endpoint exists (`polygon.py:284-289`).
- **Changes:**
  1. Provider work (after Section 10 verification): implement `crypto_universe_source()` on the provider — candidates in preference order: (a) crypto snapshot accumulated daily into a rolling volume table, (b) `/v3/reference/tickers?market=crypto` + per-pair daily aggregates for a short lookback, (c) licensed alternative if the plan lacks both.
  2. `CryptoUsdUniverseProvider`: eligibility = active USD-quoted pairs; ranking = average daily notional volume (price × volume) over a 30–90 day lookback (product to confirm, review §22.2); size configurable (`UNIVERSE_CRYPTO_SIZE`, default e.g. 50); every-day-expected calendar with missing-day warnings (inverse of the equity skip logic, `universe_builder.py:104-111`).
  3. Persist under `universe_key='crypto_usd_top'` via the P5 schema; wire the rebuild CLI/scheduler to include it.
  4. Scan default for crypto switches to the built universe with the static 15 as fallback (same fallback pattern as equities, `universe_builder.py:215-235`).
  5. Crypto session/calendar constants from P6 applied (lookback factors, partial-bar boundaries in UTC).
- **Files:** `backend/providers/polygon_provider.py`, `backend/services/universe/crypto_universe.py` (new), `backend/services/scans.py` (fallback list only), config, migrations if any new columns needed, tests with a fake provider serving synthetic snapshot data.
- **Migration/compat:** none for clients; universe key is additive.
- **Risks:** provider entitlement is the dominant unknown (Section 10 items 3–5); notional-volume ranking needs a price source at rank time; snapshot-accumulation approach needs several days of accumulation before first meaningful rebuild — keep static fallback until the table is warm.
- **Done:** `GET /api/universe/status` reports a populated crypto universe; a crypto scan covers it end-to-end from the UI; fallback path tested; rebuild scheduled.

### Phase 9 — Cross-asset strategy validation

- **Goal:** demonstrate strategies behave correctly on crypto data across timeframes (F-004, F-010).
- **Current problem / evidence:** strategies were only ever asserted on synthetic equity-shaped bars (`test_scans_provider_errors.py:9-24`); crypto tuning of pattern tolerances unverified (review §11 "deterministic pattern detection").
- **Changes:** golden-fixture bar sets per asset class (equity daily, crypto 1H/1D with 24/7 continuity and higher volatility) checked into `backend/tests/fixtures/`; parameterized per-strategy tests across (asset class × representative timeframes) asserting signal, insufficiency, and no exceptions; assert asset-class context survives the full path (request → job args `scan_jobs.py:142-149` → persisted `ScanResult.market` → response rows); review pattern-detection tolerances (3 %/2 % in `technical.py:669-714`) against crypto volatility and either justify or parameterize per asset class.
- **Files:** `backend/tests/test_strategies_cross_asset.py` (new), fixtures, possibly `backend/strategies/*` tolerance parameters.
- **Risks:** tolerance changes alter match rates — separate mechanical validation (no crash, correct insufficiency) from tuning decisions (product sign-off).
- **Done:** CI runs every registered strategy against both asset classes; capability declarations proven by tests (a strategy declaring equity-only is rejected for crypto requests with a clear error).

### Phase 10 — Pattern-detection and YOLOv8 capability controls

- **Goal:** gate YOLO by asset class; honest labeling; defined crypto-enablement protocol (F-007, D-2).
- **Current problem / evidence:** stock-trained model (`yoloService.py:13`) reachable from crypto charts with no gating (`pattern_detection.py:52-83`; `schemas/patterns.py` has no market field); badge says "TA-Lib" (`signalResolver.py:35`) though TA-Lib is absent (`requirements.txt`).
- **Changes:**
  1. `PatternDetectRequest` gains optional `market` (inferred from symbol prefix when absent via the domain layer); `detect_pattern_for_user` consults the capability registry — crypto → 422 with code `detector_unsupported_for_asset_class` and a message the UI renders.
  2. Frontend: hide/disable "Detect Patterns" on crypto charts from the same capability payload (`CandlestickChart.jsx:302-332` gains a capability prop, mirroring the existing `canDetectPatterns` auth gate).
  3. Rename `source_badge` values to `"YOLOv8 + TA"` / `"YOLOv8"` (constants in `signalResolver.py:35`; frontend badge mapping; XLSX header note); keep response keys (`talib_*`) as deprecated aliases for one release.
  4. Crypto-enablement protocol (documented, not implemented until product green-light per review §22.3): labeled evaluation set rendered by this app's own chart pipeline, precision/recall at deployed threshold, per-class thresholds, sign-off flips the capability flag only.
  5. Capture-consistency hardening (both asset classes): document/fix capture spec (theme, indicator visibility) so the model input distribution is stable; optionally strip indicator overlays from the detection capture.
- **Files:** `backend/schemas/patterns.py`, `backend/services/pattern_detection.py`, `backend/services/patternDetection/signalResolver.py`, `backend/api/pattern_routes.py`, `frontend/src/components/charts/CandlestickChart.jsx`, tests (`test_pattern_routes.py` additions).
- **Migration/compat:** badge rename is user-visible — release note; deprecated response aliases prevent client breakage.
- **Done:** crypto detect attempts are rejected server-side and prevented client-side; equity flow unchanged; badge truthful; enablement protocol documented in the repo.

### Phase 11 — Observability, performance, caching, resilience

- **Goal:** make multi-asset scans fast and observable enough to operate.
- **Current problem / evidence:** sequential symbol loop (`scans.py:381`) under a 10-slot client semaphore (`polygon.py:23,127`) — ~800-symbol scans serialize on network latency; eager compute (F-012, partially fixed in P4); rich log counters exist (`scans.py:545-569`) but no metrics surface; footer/health staleness (F-011, fixed in P1).
- **Changes:** bounded worker-side concurrency for bar fetch+analysis (ThreadPool sized to the client semaphore, preserving cancel checks via the existing `progress_callback` mechanism `jobs/scan_jobs.py:17-20`); per-scan timing breakdown (fetch vs analyze vs persist) added to `meta`; cache policy review — bar-cache TTL alignment with timeframe (a 1m scan re-run within TTL should hit cache; a 1D scan next day must not serve stale bars; current default TTL behavior in `services/cache.py` to be measured); provider-error taxonomy already strong (`scans.py:571-627`) — surface `provider_error.type` in the UI error card (`ScanResults.jsx:17-25`); scan duration/percentile logging for regression tracking.
- **Files:** `backend/services/scans.py`, `backend/services/cache.py`, `frontend/src/components/stock/ScanResults.jsx`, tests for cancellation under concurrency.
- **Risks:** DB session use inside threads (SQLAlchemy sessions are not thread-safe) — persist results on the coordinating thread only; RQ job timeout interplay (`SCAN_JOB_TIMEOUT_SECONDS`).
- **Done:** measured wall-time reduction on a full-universe scan recorded in the PR; cancellation test passes under concurrency; timing metadata visible in scan meta.

### Phase 12 — Final integration and acceptance testing

- **Goal:** prove the Overall Definition of Done (Section 13) end-to-end.
- **Changes:** e2e specs (extending `frontend/e2e/user-flow.spec.js` mock-API style): equity NASDAQ-only scan; crypto scan on `4H`; unsupported combination rejection (equity-only strategy + crypto → visible validation message); insufficient-data rendering on `1M`; YOLO disabled on crypto chart. Backend integration tests asserting context survival (market, universe, timeframe from request to persisted rows to status payload). A manual acceptance checklist against a real Polygon key for the provider-dependent cells marked `V` in review §14.3, recording actual plan behavior next to each Section 10 item.
- **Done:** every item in Section 13 has a linked automated test or recorded manual verification; review §14.3 `Unverified` cells re-graded with evidence.

---

## 5. Dependencies Between Phases

```
P1 ──► P2 ──► P3 ──► P5 ──► P8 ──► P9 ──► P12
        │      │      ▲      ▲
        └────► P4 ────┴──► P6 │
                │            │
                ├──► P7 ─────┘
                └──► P10
P11 after P3–P8 stabilize (can start measurement earlier)
```

Hard edges: P4 before P6 (per-strategy `required_history` feeds lookback math); P5 before P8 (crypto universe needs the widened schema); P4 before P7 and P10 (capability registry feeds UI and YOLO gating); P8 before P9 (validation needs the real crypto path).

---

## 6. Frontend Migration Plan

1. **P1:** tests + footer count fix only; no UX change.
2. **P7 step 1 (non-breaking):** consume capability payload defensively (missing ⇒ all-enabled), matching the existing `available !== false` idiom so the frontend can deploy before/after the backend.
3. **P7 step 2:** universe selector + per-market state retention + result tagging; store shape versioned (`scanMeta.market` preferred over `activeMarket` in all copy).
4. **P10:** capability-gated Detect Patterns; badge rename.
5. **Continuous:** FilterPanel remains fully data-driven — no strategy names hardcoded client-side (already true today, preserve it; `CATEGORY_LABELS` fallback at `FilterPanel.jsx:153` already tolerates unknown categories).

## 7. Backend Migration Plan

1. Additive-first: new packages (`domain/`, `providers/`, `strategies/`, universe providers) land alongside old code; old entry points (`get_flat_filters`, `canonicalize_symbol`, `CRYPTO_SYMBOLS` fallback) become shims.
2. One DB migration (P5) with backfill; rebuild universe immediately after deploy; scheduler markers (`universe:refresh_scheduled` Redis key, `universe_builder.py:20`) cleared on deploy.
3. Shim removal only in P12 after equivalence and integration tests pass.
4. Worker compatibility: RQ job signature `run_scan_job(job_id, user_id, market, filters, timeframe, limit)` (`worker.py:1-4`) gains `universe=None` keyword-last so in-flight jobs from the previous release still execute during rolling deploys.

## 8. Testing Strategy

- **Characterization (P1):** pin crypto scan, universe fallback, health payload.
- **Unit:** per-strategy equivalence + capability tests (P4); domain symbol round-trips (P2); lookback/session math incl. DST-agnostic UTC assertions (P6); resampling golden files (P6); signal-resolver rename aliases (P10).
- **Contract:** `FakeProvider` implements the full protocol; a shared contract-test suite runs against both `FakeProvider` and (optionally, keyed) `PolygonProvider` (P3).
- **Integration:** scan request → persisted rows → status payload for (market × universe × timeframe) samples; template evaluation path (`scan_templates.evaluate_template`, which bypasses the queue) included since it calls `scan_market` directly.
- **Frontend:** store tests for payload construction incl. `universe`; component tests for capability-disabled controls; e2e per P12.
- **Cross-asset (P9):** parameterized strategy matrix on golden fixtures.
- **Coverage gate:** keep the existing `--cov-fail-under=70` CI bar; new packages target ≥85 %.

## 9. Compatibility Strategy

- Wire values `stocks`/`crypto`, canonical timeframe strings, and all existing filter keys are frozen (ADR-1).
- All new request fields optional with behavior-preserving defaults (`universe`, strategy params, pattern `market`).
- All new response fields additive (`insufficient_data_symbols`, capability blocks, timing meta); deprecated aliases (`talib_*`) retained one release.
- DB: additive columns + constraint replacement with backfill; `ScanResult`/`ScanHistory` untouched except optional new nullable columns if per-strategy signals are persisted (decision deferred to P6).
- Saved templates: pre-migration audit query for unknown filter keys before strict validation ships (P4 risk item).

## 10. Data-Provider Validation Tasks

Each task records: endpoint, plan response, sample payload, decision. All are prerequisites for the phases noted. Every item is currently `Requires external provider verification` (review §18, §22.1).

| # | Verify | Blocks |
|---|---|---|
| V-1 | Intraday history depth per span (1m–4H) for stocks on the current plan; confirm `data_limit_notice` thresholds match reality | P6 lookbacks |
| V-2 | `45m` (multiplier=45/minute) and `timespan=year` aggregates return usable bars for stocks | P6 resampling decision; review §14.3 STK `V` cells |
| V-3 | Crypto aggregates entitlement: spans, history depth, `X:` symbol coverage for the target pair set | P8; review §14.3 CRY column |
| V-4 | Crypto snapshot payload fields (`/v2/snapshot/locale/global/markets/crypto/tickers`): per-pair volume semantics (base vs notional), day vs prevDay availability | P8 ranking design |
| V-5 | `/v3/reference/tickers?market=crypto` pagination size and metadata (active flag, base/quote parsing) | P8 eligibility |
| V-6 | Aggregate row cap behavior beyond `limit=50000` (does 1m×crypto×10d paginate or truncate?) | P6/P8 correctness |
| V-7 | Rate-limit ceilings under the worker-side concurrency planned in P11 (semaphore sizing) | P11 |
| V-8 | Real-time vs delayed data entitlement per asset class (affects partial-bar labeling honesty) | P6 |

## 11. Risk Register

| Risk | Phase | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| Polygon plan lacks crypto history/universe data | P8 | Medium | High — blocks the core product goal | V-3/V-4/V-5 first; snapshot-accumulation fallback; static-15 fallback retained |
| Strategy port drifts from lambda behavior | P4 | Medium | High — silent result changes | Per-strategy equivalence tests against P1 pins; port one category per PR |
| Universe migration breaks weekly rebuild in prod | P5 | Low | High | Backfill + immediate post-deploy rebuild; constraint change tested on Postgres, not just SQLite |
| `insufficient_data` semantics confuse users (fewer/more matches) | P6 | Medium | Medium | Additive meta first, UI explanation in P7, release notes |
| Worker concurrency corrupts DB sessions / breaks cancel | P11 | Medium | Medium | Persist on coordinator thread only; cancellation test; keep sequential mode behind env flag |
| Rolling deploy with changed job signature | P5/P7 | Low | Medium | Keyword-last optional args; workers deploy before web |
| YOLO gating perceived as feature regression by crypto users | P10 | Low | Low | Clear UI message + documented enablement path |
| Capability payload drift between validation and UI | P4/P7 | Low | Medium | Single registry source; contract test asserting payload ⊇ validator rules |

## 12. Prioritized Backlog

1. **P1** characterization tests (crypto scan) + health/footer counts + doc fixes — smallest effort, unblocks everything (F-010, F-011, F-013).
2. **P4** strategy registry + capability metadata — highest architectural leverage (F-003, F-004, F-005).
3. **P2/P3** domain models + provider seam (F-014, F-009) — small, enables P5/P8.
4. **P5** universe generalization + request-level universe selection (F-006) — also delivers the user-visible NASDAQ/NYSE scoping win for equities early.
5. **P6** timeframe correction (F-008, F-015).
6. **P7** frontend capability surface (F-002, F-005).
7. **P8** crypto universe (F-001) — the headline feature, deliberately after its foundations.
8. **P10** YOLO gating (F-007) — independent; can be pulled earlier as a quick risk fix (the server-side market check alone is a small, high-value change).
9. **P9** cross-asset validation.
10. **P11** performance/observability.
11. **P12** acceptance.

## 13. Overall Definition of Done

A normal user, through the supported frontend, can:

1. Choose equities or cryptocurrencies (existing toggle, preserved).
2. Choose an applicable market/universe: All US / NASDAQ / NYSE / Crypto top-USD-pairs (P5, P7, P8).
3. Choose an applicable timeframe, with plan-unavailable intervals visibly disabled (P4/P6/P7, resolving D-1).
4. Choose one or more supported strategies, with unsupported asset/timeframe combinations disabled and explained (P4, P7).
5. Start a scan (existing flow, preserved).
6. Retrieve correct market data with computed lookbacks and per-class calendars (P6, P8).
7. Execute strategies with **no asset-specific orchestration branches** — `scan_market` contains no `market ==` conditionals; universe registry and strategy capabilities absorb the variation (P4, P5; today's single branch at `scans.py:336` removed).
8. Receive bullish, bearish, neutral, **or insufficient-data** results per symbol (P4, P6).
9. View correctly labeled results and charts, tagged with the market/universe/timeframe they came from (P7).
10. Receive a clear validation message for unsupported combinations (P4, P7, P10).

Automated tests demonstrate: asset-class context survives the full request path (P9); timeframe survives the full request path (P1/P6 extend the existing `test_timeframes.py` guarantee to persisted rows and responses); strategies declare and enforce capabilities (P4/P9); equity and crypto universes share one contract (P5/P8); provider details do not leak into strategy code (P3/P4 registry import test); unsupported YOLOv8 usage is rejected (P10); frontend controls expose only valid combinations (P7 component tests); a cryptocurrency scan initiates through the normal frontend (P1 e2e, P12); the picker/universe supplies valid instruments for the selected asset class (P5/P8 tests).

## 14. Recommended Implementation Order

**P1 → P4 → P2 → P3 → P5 → P6 → P7 → P8 → P9 → P10 → P11 → P12**, with two sanctioned deviations:

- P10's server-side market check on `/api/patterns/detect` may ship immediately after P1 as a standalone hardening fix (it needs only the symbol-prefix inference that already exists in `backend/symbols.py`).
- P4 is listed before P2/P3 because the registry refactor is pure-Python and test-driven; if the team prefers strict layering, run P2 → P3 → P4 — the plan's dependency graph (Section 5) permits either.

Done means: all Section 13 items verified, review §14.3 `Unverified` cells re-graded from V-task evidence, and the traceability matrix in Section 2 shows every finding's completion criterion met.
