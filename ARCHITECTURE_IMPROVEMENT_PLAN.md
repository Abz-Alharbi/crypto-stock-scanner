# Architecture Improvement Plan — Market Scanner Pro

Companion to `ARCHITECTURE_REVIEW.md` (2026-07-11). All finding IDs (F-001…F-020) and discrepancy IDs (D-001…D-005) refer to that review. This plan contains no authentication, authorization, account, or administration work.

---

## 1. Improvement Principles

1. **Refactor under characterization tests.** The crypto scan path has zero test coverage today (F-010); nothing structural moves until the current behavior is pinned.
2. **Keep the wire contract and persistence stable.** `market ∈ {stocks, crypto}`, canonical timeframe strings, existing filter keys, and DB CHECK constraints (`backend/models/scan.py:10-13`) stay valid throughout; new fields are additive and optional.
3. **One source of truth for capabilities.** The same server-side registry that validates a request feeds the frontend; the UI never re-derives business rules (review §19.5, ADR-2).
4. **Preserve what already works.** The async RQ job flow, hardened Polygon transport (`backend/clients/polygon.py`), pydantic validation layer, data-driven FilterPanel, provider-decoupled analysis-dict pattern, the existing Momentum preset composed of its current constituent predicates, and the existing custom deterministic pattern-analysis logic currently labeled TA-Lib in the codebase are kept operational until their phase-owned replacements pass their required tests.
5. **Seams before features.** Provider interface, strategy registry, and universe contract land before crypto enablement widens — broad crypto work on today's structure would multiply the one `market ==` branch into many.
6. **Silent degradation becomes explicit.** Every place where a computation silently returns `None` (F-004, F-015) becomes a declared `insufficient_data` outcome.
7. **No invented provider behavior.** Every plan step that depends on Polygon plan entitlements starts with a verification task (Section 10).

---

## 2. Findings-to-Phases Traceability Matrix

| Finding ID | Current gap | Evidence location in review | Target phase | Completion criterion |
|---|---|---|---|---|
| F-001 | Crypto universe is a hardcoded 15-pair constant; no crypto universe construction | §8, §10, §12 (`scans.py:36-40`) | P8 (foundation in P5) | A ranked universe of at least 100 eligible USD pairs is built from the approved provider source over 90 days, persisted, refreshable, and used by crypto scans; the constant remains only as fallback |
| F-002 | Crypto scan entry point exists but is a bare toggle; stale-result mislabeling; hidden 15-pair limit | §8–§10 (Header.jsx:66-80; ScanResults.jsx:48) | P7 | Universe size/name visible in scan UI; results tagged with their own market; switching markets never mislabels prior results |
| F-003 | Strategies are inline lambdas co-located with orchestration; no contract/registry | §11 (`scans.py:124-179`) | P4 | New strategy added by dropping a module in `backend/strategies/` with zero edits to orchestration; registry test proves it |
| F-004 | No per-strategy history/timeframe/asset declarations; silent long-lookback degradation | §11, §13–§14 (`scans.py:404`; `technical.py:12-23`) | P4 + P6 | Each strategy declares `required_history`/timeframes/asset classes; unmet requirements yield `insufficient_data`, not silent False |
| F-005 | No capability metadata; documented `available` flag never emitted (D-001) | §9, §13–§14, review D-001 (`market_config.py:174-182`) | P4 + P7 | `/api/capabilities` (or extended `/api/filters`) drives both request validation and UI enable/disable states |
| F-006 | Universe schema/builder structurally equity-only; no exchange/universe scoping in requests | §12 (`models/universe.py:9`; `schemas/market.py:14-18`) | P5 | Universe table is asset-class/venue aware; `ScanRequest.universe` selects NASDAQ/NYSE/merged/crypto universes |
| F-007 | Stock-trained YOLO ungated by asset class; capture distribution uncontrolled; custom deterministic analysis is mislabeled TA-Lib (D-002) | §16 (`yoloService.py:13`; `signalResolver.py:35`) | P10 | Crypto detect requests rejected/disabled via capability flag; badge renamed; crypto enablement gated on documented validation |
| F-008 | Fixed calendar-day lookbacks; global 30-bar gate; `min_bars` decorative; no resampling; no session model | §13–§14 (`market_config.py`; `scans.py:404`) | P6 | Lookback computed from required bars × session calendar; `min_bars` enforced; optional resample fallback for plan-unavailable intervals |
| F-009 | Direct `polygon` singleton coupling; no provider interface | §17, ADR-7 (`clients/polygon.py:359`) | P3 | Scans/universe/pattern services depend on a `MarketDataProvider` protocol; Polygon is one binding; a fake provider powers tests |
| F-010 | No automated crypto scan coverage | §8 item 4, §18 | P1 (characterization) + P9 (validation) | `scan_market('crypto', …)` covered in backend tests; frontend store test covers a crypto `runScan`; e2e includes market toggle |
| F-011 | Health/footer report fixed fallback counts | §18/F-011 (`scans.py:227-234`; `App.jsx:219`) | P1 | Health payload and footer show live universe counts per asset class |
| F-012 | Eager full analysis for every symbol; sequential scan loop | §11.4 (`technical.py:716-853`; `scans.py:381`) | P4 (selective compute) + P11 (concurrency) | Only features required by selected strategies are computed; measured scan wall-time reduction recorded |
| F-013 | Documentation drift (D-001–D-005) | §5 | P1 | `PROJECT_DOCUMENTATION.md` corrected or code aligned for all five discrepancies, item by item |
| F-014 | No pair semantics; USD quote hardcoded in `canonicalize_symbol` | §10, §19.1 (`symbols.py:24-41`) | P2 | `Instrument` carries base/quote/venue; canonicalization is a compatibility shim over it |
| F-015 | Result/status schemas omit context, evidence, and per-symbol insufficient-data outcomes | §13, §15, §18 (`scans.py:471-490,654-681`) | P4 + P6 + P7 | Scan responses persist and display immutable context and explicit per-strategy outcomes, including insufficient data |
| F-016 | Browser/backend indicator calculations diverge; valid zero values become `None` | §11, §14–§15 (`technical.py:18-23,58-66,819-825`; `CandlestickChart.jsx:510-639,820-898`) | P1 + P4 + P7 + P9 | Characterization pins the divergence and zero behavior; one authoritative feature path supplies strategies/cards/charts and passes cross-asset golden tests |
| F-017 | Request/domain context is under-specified; extras are ignored and mixed unknown filters are dropped | §9, §11, §18–§19 (`schemas/common.py:7-8`; `schemas/market.py:14-18`; `scans.py:337-340`) | P1 + P2 + P4 + P7 | Characterization pins current permissiveness; explicit domain/request fields and registry validation reject unknown or invalid combinations with structured errors |
| F-018 | NASDAQ-first early exit can prevent NYSE evaluation and is not a global top-N | §7, §12, §15 (`universe_builder.py:215-235`; `scans.py:381-383,645`) | P1 + P5 + P11 | Characterization reproduces the defect; universe execution evaluates fairly and concurrency preserves deterministic cross-exchange results |
| F-019 | Empty/failed universe rebuild can replace good data and silently activate fallback | §12, §18 (`universe_builder.py:174-235`) | P1 + P5 + P11 | Characterization pins the failure; staged validation/last-known-good promotion prevents empty replacement and exposes degraded status |
| F-020 | Persistence failures are swallowed; worker errors flatten context; insufficiency can be mislabeled provider failure | §13, §17–§18 (`scans.py:571-644`; `jobs/scan_jobs.py:43-48`) | P1 + P3 + P6 + P11 | Characterization covers each boundary; typed failures survive to status/UI and persistence failure cannot appear as successful zero results |

Every finding F-001–F-020 is assigned to at least one phase. Every critical/high finding is covered by an implementation phase and phase-level verification; every phase below references at least one finding ID.

---

## 3. Phase Overview

| # | Phase | Primary findings | Depends on |
|---|---|---|---|
| P1 | Characterization tests & documentation reconciliation | F-010, F-011, F-013, F-016–F-020 | — |
| P2 | Canonical domain models (asset, instrument, candle, timeframe) | F-014, F-008 (types only) | P1 |
| P3 | Market-data provider abstraction | F-009 | P2 |
| P4 | Strategy contract, registry & capability metadata | F-003, F-004, F-005, F-012, F-015–F-017 | P1–P3 |
| P5 | Generalized universe providers | F-001 (foundation), F-006, F-018, F-019 | P1–P4 |
| P6 | End-to-end timeframe correction | F-004, F-008, F-015, F-020 | P1–P5 plus confirmed P6 rules and applicable provider checks |
| P7 | Frontend asset-class, universe & capability surface | F-002, F-005, F-015–F-017 | P1–P6 |
| P8 | Cryptocurrency data path & universe implementation | F-001, F-014 | P1–P7 plus V-3–V-6 and an approved provider-source decision |
| P9 | Cross-asset strategy validation | F-004, F-010, F-016 | P1–P8 plus an approved validation matrix |
| P10 | Pattern-detection & YOLOv8 capability controls | F-007 | P1–P9 |
| P11 | Observability, performance, caching, resilience | F-009, F-011, F-012, F-018–F-020 | P1–P10 plus V-7 and a recorded baseline |
| P12 | Final integration & acceptance testing | F-001–F-020 | P1–P11 |

Sequencing rationale: phases are strict hard gates and execute only in this order: **P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8 → P9 → P10 → P11 → P12**. No phase or partial phase starts until every preceding phase is complete and any phase-specific confirmation/provider gate is satisfied.

---

## 4. Detailed Phased Implementation Plan

### Phase 1 — Characterization tests and documentation reconciliation

- **Goal:** pin current behavior and known defects; make the crypto path, universe counters, calculation seams, validation permissiveness, fairness, universe publication, and failure behavior observable before anything moves.
- **Current problem / evidence:** no test calls `scan_market('crypto', …)` (F-010; review §8 item 4); footer/health report constants (F-011); browser/backend indicators diverge and zero values can disappear (F-016); requests silently ignore/drop context (F-017); exchange ordering can starve NYSE (F-018); empty universe rebuilds can replace good data (F-019); persistence/errors/insufficiency are conflated or swallowed (F-020); documentation discrepancies are D-001–D-005.
- **Changes:**
  1. Backend characterization tests (pattern of `backend/tests/test_scans_provider_errors.py`, reusing `StaticBarsPolygonClient`): crypto scan happy path (15 symbols attempted, `market='crypto'` persisted, `X:` symbols in results); crypto + intraday timeframe; crypto scan with a long-lookback filter on short bars (pins today's silent-False behavior so P4/P6 can assert the change deliberately).
  2. Frontend: store test for `runScan` with `activeMarket:'crypto'` asserting payload; extend `frontend/e2e/user-flow.spec.js` mock flow with a market-toggle step.
  3. Characterize F-016 with backend zero-indicator cases and frontend/backend EMA/Bollinger golden values that intentionally record today's difference; later phases change the expectation deliberately.
  4. Characterize F-017 through request tests for ignored extra context and mixed valid/unknown filter IDs; characterize F-018 with a NASDAQ-first universe that fills `max_results` before NYSE; characterize F-019 with an empty candidate build preserving today's fallback behavior; characterize F-020 with insufficient bars, result/history persistence failure, and worker error serialization.
  5. Fix `health_payload()` to include live universe counts (from `universe_builder.status_payload()`) alongside fallback counts; update the footer to prefer live counts (`App.jsx:218-220`).
  6. Reconcile exactly five documentation discrepancies in `PROJECT_DOCUMENTATION.md`: D-001 corrects current timeframe metadata/`available` behavior (P4 later implements capabilities); D-002 describes the custom deterministic pattern-analysis logic currently labeled TA-Lib; D-003 uses the actual `watchlists` table name; D-004 documents the actual retry boundary including non-retried HTTP 5xx; D-005 documents the Header stocks/crypto toggle. There is no D-006 or D-007 in the approved review.
- **Files:** `backend/tests/test_scans_crypto.py` (new), focused additions to provider/error/universe/indicator/request/job characterization tests, `frontend/src/store/useMarketStore.test.js`, chart calculation tests, `frontend/e2e/user-flow.spec.js`, `backend/services/scans.py` (health only), `frontend/src/App.jsx`, `PROJECT_DOCUMENTATION.md`.
- **Migration/compat:** none — additive tests plus one payload field.
- **Risks:** characterization can accidentally bless defects; test names must state current behavior and the owning future phase. Health payload consumers (footer, e2e mock at `user-flow.spec.js:61`) must tolerate additive fields.
- **Completion criteria / done:** CI green with new tests; crypto scan behavior pinned in three backend cases plus frontend store/e2e coverage; F-016–F-020 each has a reproducible characterization and explicit future-phase disposition; footer shows live universe counts; all five D-001–D-005 documentation discrepancies are corrected to describe current behavior and their phase-owned future change.

### Phase 2 — Canonical domain models

- **Goal:** introduce `AssetClass`, `Instrument` (base/quote/venue), `MarketDataRequest`, and typed timeframe helpers without changing wire formats.
- **Current problem / evidence:** `CanonicalSymbol` triple with USD-hardcoded pair heuristic (`symbols.py:24-41`, F-014); asset/request context is a bare, under-specified string and unknown context is ignored (F-017).
- **Changes:** new `backend/domain/` package (`asset.py`, `instrument.py`, `timeframes.py` re-exporting `market_config`); `canonicalize_symbol` reimplemented as a shim returning `Instrument`-backed values; explicit `Instrument.for_crypto(base, quote='USD', venue='GLOBAL_CRYPTO')` constructor replacing the append-`USD` heuristic; canonical scan-context types for asset class, market/venue, universe or instrument scope, and timeframe; unit tests for round-tripping every symbol form seen in the repo (`AAPL`, `X:BTCUSD`, bare `BTC` + market hint) and rejecting internally inconsistent context.
- **Files:** `backend/domain/*` (new), `backend/symbols.py` (shim), touch-points that read `.market` remain unchanged.
- **Migration/compat:** wire values `stocks`/`crypto` map 1:1 to `AssetClass`; no DB change.
- **Risks:** watchlist/scan persistence rely on `canonicalize_symbol` semantics — the shim must be behaviorally identical (guarded by P1 tests plus existing `test_integration_routes.py:38-50`).
- **Done:** all existing tests pass with the shim in place; new domain tests cover pair construction; no endpoint payload diff.

### Phase 3 — Market-data provider abstraction

- **Goal:** a `MarketDataProvider` protocol seam around the existing client (ADR-7).
- **Current problem / evidence:** module-level `polygon` singleton imported by `scans.py:7`, `universe_builder.py:12`, fundamentals/news (F-009); tests must monkeypatch module attributes (`test_scans_provider_errors.py:74`).
- **Changes:** define protocol (`get_bars(instrument, timeframe, lookback)`, `search`, `reference_universe`, `crypto_snapshot`, `grouped_daily_stocks`); implement `PolygonProvider` delegating to the current `PolygonClient` (transport code untouched); inject via a module factory (`get_provider()`) that scans/universe/pattern services call; convert conftest's `MockPolygonClient` into a first-class `FakeProvider` fixture; introduce typed provider failures that retain provider, instrument, asset class, timeframe, status/error type, and original exception context through the scan/job boundary (F-020), never converting infrastructure failure to an empty result.
- **Files:** `backend/providers/__init__.py` + `backend/providers/polygon_provider.py` (new), `backend/services/scans.py`, `backend/services/universe/universe_builder.py`, `backend/services/pattern_detection.py`, `backend/tests/conftest.py`.
- **Migration/compat:** `backend/clients/polygon.py` stays; the `polygon` singleton remains unchanged for fundamentals/news because those services are outside this migration's scope.
- **Risks:** cache keys currently embed raw endpoints (`polygon.py:104`) — keep caching inside the client so keys don't churn.
- **Done:** scan and universe tests run against `FakeProvider` without monkeypatching module globals; `PolygonClient` diff is zero.

### Phase 4 — Strategy contract, registry, and capability metadata

- **Goal:** replace `FILTER_DEFINITIONS` lambdas with registered strategy objects that declare requirements; emit capability metadata.
- **Current problem / evidence:** F-003 (`scans.py:124-179` co-located with orchestration), F-004 (global 30-bar gate `scans.py:404`; EMA-200 silent `None` `technical.py:18-23`), F-005 (`filters_payload` has no capability info, `scans.py:237-251`; documented `available` flag never emitted, `market_config.py:174-182`), F-012 (eager `full_analysis`), F-015 (no structured per-strategy evidence/outcome), F-016 (duplicate/divergent calculations and zero coercion), and F-017 (unknown filter IDs silently dropped).
- **Changes:**
  1. `backend/strategies/` package: base `Strategy` dataclass/Protocol per review §19.2; one module per category porting all 22 filters **with identical IDs and boolean semantics** (each port asserts equivalence against the P1-pinned behavior); presets move alongside.
  2. Registry with import-time registration + duplicate-ID guard; `get_flat_filters()` reimplemented over the registry (keeps `scan_market` call sites working during transition).
  3. `StrategyResult` with explicit evaluated/matched/not-matched/insufficient/unsupported/error status, bullish/bearish/neutral/no-signal direction, and supporting evidence (F-015); `required_history` enforced per strategy — a symbol with 40 bars can still match RSI strategies while EMA-200 strategies report `insufficient_data` instead of silently False.
  4. Selective feature computation: `TechnicalAnalysis.full_analysis(bars, features=…)` computes only the union of `required_features` across selected strategies (trade setup/fibonacci only when needed by strategies or detail views; `stock_detail` keeps requesting everything). Preserve legitimate numeric zeroes and make this backend feature path authoritative for P7 chart/card consumption (F-016).
  5. Capability payload: extend `/api/filters` (additive) with per-strategy `supported_asset_classes`, `supported_timeframes`, `required_history`, and the timeframe `available` flag (resolving D-001). The provider-plan capability source is a config-driven dictionary keyed by plan tier. The current unlimited subscription defaults all capabilities enabled; later tightening changes configuration, not architecture.
  6. Request validation: `ScanRequest` cross-checks filters against the registry for the requested market/timeframe and returns a structured validation error naming the invalid combination.
  7. Registry extension proof — implement exactly one new strategy named **RSI Overbought/Oversold** (stable ID `rsi_overbought_oversold`): Wilder-smoothed RSI period 14 on the latest closed bar; bullish below 30; bearish above 70; neutral/no signal from 30 through 70 inclusive; minimum 30 closed candles; supports equity and crypto and every canonical timeframe; evidence includes the computed RSI value. It must register/discover through the registry only and must require zero scan-orchestration edits.
- **Files:** `backend/strategies/*` (new), `backend/services/scans.py` (orchestration consumes registry; FILTER_DEFINITIONS removed at the end), `backend/services/technical.py`, `backend/schemas/market.py`, `backend/tests/*` (per-strategy unit tests).
- **Migration/compat:** filter keys unchanged → saved `scan_templates.criteria_json` and frontend selections keep working; the silently-dropping-unknown-filters behavior (`scans.py:338`) is replaced by explicit validation — verify no stored template carries an unknown key first.
- **Risks:** behavioral drift during the port (mitigated by equivalence tests); `insufficient_data` changes result counts — flag behind a response field, not a match-semantics change.
- **Done:** RSI Overbought/Oversold added in a single new file appears in `/api/filters`, is selectable in the untouched FilterPanel, returns the specified direction/evidence, and executes with no orchestration edit (registry test asserts `scans.py` has no strategy imports); all 22 legacy filters pass equivalence tests; zero values are preserved; unknown/unsupported strategy configurations fail explicitly.

### Phase 5 — Generalized universe providers

- **Goal:** asset-class/venue-aware universe storage and per-request universe selection.
- **Current problem / evidence:** F-006 (`models/universe.py:9` CHECK NASDAQ/NYSE; builder equity-only `universe_builder.py:21-24`); no `universe` request parameter (`schemas/market.py:14-18`); merged-exchange scanning only; NASDAQ-first early exit can starve NYSE (F-018); an empty rebuild can replace good data and silently trigger fallback (F-019).
- **Changes:**
  1. Migration: add `asset_class` (default `equity`), `venue`, `quote_currency` (nullable), `universe_key` columns to `universe_symbols`; replace the exchange CHECK; re-scope rank uniqueness to `(universe_key, rank)`; backfill existing rows (`NASDAQ`→`equity/XNAS/nasdaq_top` etc.).
  2. `UniverseProvider` contract + `EquityVolumeUniverseProvider` port of the current eligibility/ranking behavior (verified against `test_universe_builder.py`); registry of universe keys: `us_stocks_top` (merged — default), `nasdaq_top`, `nyse_top`, `crypto_static` (the 15-pair constant, formalized as a provider so crypto scans stop reading a constant in `scans.py`). Candidate builds are validated before the transactional delete/insert; empty, undersized, stale, or failed candidates retain the last-known-good rows and expose a degraded reason (F-019).
  3. `ScanRequest.universe: Optional[str]`; `scan_market` resolves symbols via the universe registry; default per market keeps current behavior byte-for-byte.
  4. `GET /api/universe/status` extended to report per-universe counts and freshness.
  5. Remove exchange-ordered early termination as a result-selection mechanism. Evaluate the selected universe before applying the result limit, or use a documented deterministic fair budget that guarantees configured exchange coverage; tests must prove NYSE cannot be starved and the final cap is a global deterministic result (F-018).
- **Files:** `migrations/versions/*` (new), `backend/models/universe.py`, `backend/services/universe/*`, `backend/schemas/market.py`, `backend/services/scans.py:336` (branch replaced by registry lookup), tests.
- **Migration/compat:** delete/insert rebuild pattern (`universe_builder.py:174-181`) preserved; old rows backfilled; API additions optional.
- **Risks:** migration on the production Postgres table with the rebuild scheduler enabled — coordinate a rebuild after deploy; rank-uniqueness re-scoping must match the rebuild's write pattern.
- **Done:** scans accept `universe`; NASDAQ-only and NYSE-only scans work through the API; merged scans are fair/global rather than exchange-order truncated; crypto scans read the static universe via the same contract; invalid empty rebuilds preserve last-known-good state and report degradation; universe builder tests are green on old and new selection paths.

### Phase 6 — End-to-end timeframe correction

- **Goal:** computed lookbacks, enforced minimum bars, explicit insufficient-data, optional resampling, session calendars.
- **Current problem / evidence:** F-008 (fixed `days`, `market_config.py`; global 30-bar gate `scans.py:404`; `min_bars` only feeds a notice `market_config.py:164-171`); F-015 (per-symbol insufficiency/context invisible, aggregate counters only `scans.py:654-681`); F-020 (insufficiency can become provider failure); daily-calibrated pattern windows (`technical.py:669-714`).
- **Changes:**
  0. **Mandatory confirmation gate before P6 code:** inspect/reuse the market-holidays endpoint already integrated for NASDAQ/NYSE universe building, then present concrete rules for equity sessions/holidays/time zones, crypto 24/7 alignment, required bars by timeframe, lookback fallback/cap behavior, and partial-candle closure. Pause for product/engineering confirmation; do not implement from approximate factors.
  1. After confirmation, implement `lookback_for(timeframe, required_bars, asset_class)` in the domain layer using the approved calendar/session rules; `get_bars_with_meta` uses it and applies the explicitly approved relationship to legacy `days` values.
  2. Required bars = max(`min_bars` config, max of selected strategies' `required_history`) — replaces the hardcoded 30.
  3. Add an additive `symbol_outcomes` collection for every attempted symbol with per-strategy evaluated/matched/not-matched/insufficient/unsupported/error states and required/obtained bars. Preserve legacy `results` as matched rows during compatibility. Scan meta also gains `insufficient_data_symbols: [{symbol, bars, required}]`; infrastructure/provider/persistence failure never appears as neutral, no-match, or insufficient data (F-015/F-020).
  4. Optional resampling: single utility (pandas `resample` on provider bars) used only for canonical intervals the plan cannot serve natively (candidate: `45m` from `15m`), gated per interval by provider-verification results (Section 10); calendar intervals (`1M`, `1Y`) stay provider-native.
  5. Incomplete trailing candle: mark the last bar `partial` only according to the confirmed timeframe/calendar closure rules; pattern windows exclude partial bars by default; chart still renders them distinctly.
  6. Pattern-window review: propose concrete timeframe categories/window sizes in the mandatory confirmation report; after approval, parameterize `detect_chart_patterns(window=…)` rather than retaining a fixed 60.
- **Files:** `backend/domain/timeframes.py`, `backend/services/scans.py`, `backend/services/technical.py`, `backend/market_config.py` (data only), tests including crypto-vs-equity lookback assertions.
- **Migration/compat:** meta fields additive; scan results may change where the 30-bar gate previously admitted symbols that long-lookback strategies couldn't evaluate — release-note this.
- **Risks:** larger lookbacks increase provider load for 200-bar strategies on `1D` (~200 trading days ≈ today's 730-day window already covers it — verify per timeframe); resampling correctness (bar alignment) needs golden-file tests.
- **Done:** P6-owned `Partial` cells in the review §14 matrix become `Supported` with evidence or explicitly rejected combinations; tests demonstrate a `1M` scan reporting `insufficient_data` for EMA-200 strategies instead of silence; provider/no-data/insufficient/failure outcomes remain distinct.

### Phase 7 — Frontend asset-class, universe, and capability surface

- **Goal:** expose universe choice, capability-driven controls, truthful labeling.
- **Current problem / evidence:** F-002 (bare toggle; stale-result mislabeling `ScanResults.jsx:48`; hidden 15-pair limit), F-005 (no capability data consumed because none exists), F-015 (no contextual/insufficient-data rendering), F-016 (chart calculations can contradict backend), and F-017 (request context is incomplete/permissive).
- **Changes:**
  1. Store: keep `activeMarket`; add `activeUniverse` (defaulted from capabilities per market); snapshot asset/market/universe/timeframe/strategy context when a scan starts; tag results/meta with submitted context; on `setMarket`, preserve per-market filter/timeframe selections, cancel/discard stale search responses, and never relabel prior results.
  2. FilterPanel: universe selector row (radio/select fed by capabilities, showing symbol counts — e.g., "Crypto · Top USD pairs (15)"); strategy checkboxes disable with tooltip when the capability payload marks them unsupported for the current market/timeframe (same disabled pattern already used for timeframes, `FilterPanel.jsx:79-92`).
  3. Timeframe buttons finally honor real `available` flags (D-001 resolved end-to-end).
  4. ScanResults: render `symbol_outcomes`/`insufficient_data_symbols` distinctly; derive copy from submitted/`scanMeta` context instead of `activeMarket` (fixes the §9 mislabel).
  5. Request construction includes explicit available domain context and `universe`; field errors from strict backend validation are shown rather than converted to empty results (F-017).
  6. Charts/detail cards consume backend-authoritative feature values/series from P4 or pass versioned cross-language golden equivalence; the current divergent decision-bearing browser implementation cannot remain unverified (F-016).
- **Files:** `frontend/src/store/useMarketStore.js`, `frontend/src/components/filters/FilterPanel.jsx`, `frontend/src/components/stock/ScanResults.jsx`, `frontend/src/services/api.js`, component tests.
- **Migration/compat:** all new request fields remain optional on the legacy backend path. When capability metadata is absent, the UI enters an explicit legacy mode containing only combinations known to the current backend; missing metadata never means every future combination is enabled.
- **Risks:** store shape changes ripple into `useMarketStore.test.js` and e2e mocks — update in the same PR.
- **Done:** a user can select NASDAQ-only, NYSE-only, merged, or crypto universes; unsupported strategy/timeframe combos are visibly disabled with reasons; switching markets never relabels existing results.

### Phase 8 — Cryptocurrency data path and universe implementation

- **Goal:** replace the 15-pair constant with a built, ranked, refreshable crypto universe (F-001).
- **Current problem / evidence:** `scans.py:36-40`; no crypto history source in the builder (grouped-daily is stocks-only, `polygon.py:276-282`); crypto snapshot endpoint exists (`polygon.py:284-289`).
- **Changes:**
  0. **Mandatory provider-source decision gate before P8 code:** enumerate and present tradeoffs for exactly these candidates: (a) crypto snapshot accumulated daily into a rolling volume table, (b) `/v3/reference/tickers?market=crypto` plus per-pair daily aggregates, and (c) a licensed alternative if the current plan lacks both. Include V-3–V-6 evidence, quota/history/latency, volume units, warm-up/storage, venue/pair metadata, and operational cost. Pause for a decision; do not select a source unilaterally.
  1. After approval, implement `crypto_universe_source()` for the selected source only.
  2. `CryptoUsdUniverseProvider`: eligibility = active USD-quoted pairs; ranking = average daily notional volume (price × volume) over a locked **90-day** lookback; target size is **at least 100 ranked USD pairs** when provider eligibility/coverage supplies them; `UNIVERSE_CRYPTO_SIZE` defaults to 100 and may be configured upward; every-day-expected calendar with missing-day warnings (inverse of the equity skip logic, `universe_builder.py:104-111`).
  3. Persist under `universe_key='crypto_usd_top'` via the P5 schema; wire the rebuild CLI/scheduler to include it.
  4. Scan default for crypto switches to the built universe with the static 15 as fallback (same fallback pattern as equities, `universe_builder.py:215-235`).
  5. Crypto session/calendar constants from P6 applied (lookback factors, partial-bar boundaries in UTC).
- **Files:** `backend/providers/polygon_provider.py`, `backend/services/universe/crypto_universe.py` (new), `backend/services/scans.py` (fallback list only), config, migrations if any new columns needed, tests with a fake provider serving synthetic snapshot data.
- **Migration/compat:** none for clients; universe key is additive.
- **Risks:** provider entitlement is the dominant unknown (Section 10 items V-3–V-6); notional-volume ranking needs a price source at rank time; a snapshot-accumulation choice would need warm-up storage/migration explicitly approved with the provider-source decision — keep static fallback until the selected source is warm and validated.
- **Done:** `GET /api/universe/status` reports a populated crypto universe; a crypto scan covers it end-to-end from the UI; fallback path tested; rebuild scheduled.

### Phase 9 — Cross-asset strategy validation

- **Goal:** demonstrate strategies behave correctly on crypto data across timeframes (F-004, F-010).
- **Current problem / evidence:** strategies were only ever asserted on synthetic equity-shaped bars (`test_scans_provider_errors.py:9-24`); crypto tuning of deterministic-pattern tolerances is unverified (review §§10 and 16).
- **Changes:** **before any P9 code**, define and present a complete validation matrix mapping every registered strategy to the canonical timeframes it must support/test, fixture coverage per asset class, and quantitative criteria for acceptable crypto pattern-tolerance drift; pause for confirmation. After approval, add golden-fixture bar sets and parameterized strategy tests for the approved matrix; assert asset-class context survives request → job → persistence → response; review current pattern tolerances against the approved drift threshold and either retain with evidence or parameterize after product sign-off.
- **Files:** `backend/tests/test_strategies_cross_asset.py` (new), fixtures, possibly `backend/strategies/*` tolerance parameters.
- **Risks:** tolerance changes alter match rates — separate mechanical validation (no crash, correct insufficiency) from tuning decisions (product sign-off).
- **Done:** CI runs every registered strategy against both asset classes; capability declarations proven by tests (a strategy declaring equity-only is rejected for crypto requests with a clear error).

### Phase 10 — Pattern-detection and YOLOv8 capability controls

- **Goal:** gate YOLO by asset class; honest labeling of the existing custom deterministic pattern-analysis logic currently labeled TA-Lib; defined crypto-enablement protocol (F-007, D-002).
- **Current problem / evidence:** stock-trained model (`yoloService.py:13`) reachable from crypto charts with no gating (`pattern_detection.py:52-83`; `schemas/patterns.py` has no market field); badge says "TA-Lib" (`signalResolver.py:35`) though TA-Lib is absent (`requirements.txt`).
- **Changes:**
  1. `PatternDetectRequest` gains optional `market` (inferred from symbol prefix when absent via the domain layer); `detect_pattern_for_user` consults the capability registry — crypto → 422 with code `detector_unsupported_for_asset_class` and a message the UI renders.
  2. Frontend: hide/disable "Detect Patterns" on crypto charts from the same capability payload (`CandlestickChart.jsx:302-332` gains a capability prop, mirroring the existing `canDetectPatterns` auth gate).
  3. Rename `source_badge` values to `"YOLOv8 + TA"` / `"YOLOv8"` (constants in `signalResolver.py:35`; frontend badge mapping; XLSX header note); keep response keys (`talib_*`) as deprecated aliases for one release.
  4. Crypto-enablement protocol (documented, not implemented until product green-light per review §21): labeled evaluation set rendered by this app's own chart pipeline, precision/recall at deployed threshold, per-class thresholds, sign-off flips the capability flag only.
  5. Capture-consistency hardening (both asset classes): document/fix capture spec (theme, indicator visibility) so the model input distribution is stable; optionally strip indicator overlays from the detection capture.
- **Files:** `backend/schemas/patterns.py`, `backend/services/pattern_detection.py`, `backend/services/patternDetection/signalResolver.py`, `backend/api/pattern_routes.py`, `frontend/src/components/charts/CandlestickChart.jsx`, tests (`test_pattern_routes.py` additions).
- **Migration/compat:** badge rename is user-visible — release note; deprecated response aliases prevent client breakage.
- **Done:** crypto detect attempts are rejected server-side and prevented client-side; equity flow unchanged; badge truthful; enablement protocol documented in the repo.

### Phase 11 — Observability, performance, caching, resilience

- **Goal:** make multi-asset scans fast and observable enough to operate.
- **Current problem / evidence:** sequential symbol loop (`scans.py:381`) under a 10-slot client semaphore (`polygon.py:23,127`) — ~800-symbol scans serialize on network latency; eager compute (F-012, partially fixed in P4); exchange fairness must survive concurrency (F-018); universe degradation and persistence/errors need operational visibility (F-019/F-020); rich log counters exist (`scans.py:545-569`) but no metrics surface; footer/health staleness (F-011, fixed in P1).
- **Changes:** **before performance code**, measure and report the current full-universe (800+ symbol) scan P95 wall-time baseline using a documented repeatable environment/workload; pause after reporting it. After confirmation, add bounded worker-side concurrency for bar fetch+analysis (ThreadPool sized to the verified provider limit, preserving cancel checks); keep global deterministic/fair result selection and persistence on the coordinating thread; add fetch/analyze/persist timing; align cache TTL with timeframe/closed-candle boundaries; surface typed provider/persistence/universe-degraded errors in status/UI; add duration/percentile logging and last-known-good universe metrics.
- **Files:** `backend/services/scans.py`, `backend/services/cache.py`, `frontend/src/components/stock/ScanResults.jsx`, tests for cancellation under concurrency.
- **Risks:** DB session use inside threads (SQLAlchemy sessions are not thread-safe) — persist results on the coordinating thread only; RQ job timeout interplay (`SCAN_JOB_TIMEOUT_SECONDS`).
- **Done:** repeated/cached full-universe P95 wall-time improves by **at least 30%** from the recorded current baseline; uncached behavior is reported separately; cancellation and exchange-fairness tests pass under concurrency; DB sessions remain safe; timing/error/universe metadata is visible and no persistence failure appears successful.

### Phase 12 — Final integration and acceptance testing

- **Goal:** prove the Overall Definition of Done (Section 13) end-to-end.
- **Changes:** e2e specs (extending `frontend/e2e/user-flow.spec.js` mock-API style): equity NASDAQ-only scan; crypto scan on `4H`; unsupported combination rejection (equity-only strategy + crypto → visible validation message); insufficient-data rendering on `1M`; YOLO disabled on crypto chart. Backend integration tests assert context survival (market, universe, timeframe from request to persisted rows to status payload). A manual acceptance checklist uses a real Polygon key for provider-dependent entries and records evidence for each Section 10 validation task and each `Unverified` provider cell in the review §14 matrix.
- **Done:** every item in Section 13 has a linked automated test or recorded manual verification; every review §14 `Unverified` cell is regraded to `Supported`, `Partial`, or `Unsupported` with evidence and enforcement; findings F-001–F-020 have final dispositions.

---

## 5. Dependencies Between Phases

```
P1 ──► P2 ──► P3 ──► P4 ──► P5 ──► P6 ──► P7 ──► P8 ──► P9 ──► P10 ──► P11 ──► P12
```

Every arrow is a hard gate. No partial phase starts and no phase overlaps a predecessor. Additional gates: P4 audits saved-template filter IDs before strict validation; P6 pauses for approved calendar/lookback/partial-candle rules and applicable provider checks; P8 pauses for an approved provider source after V-3–V-6; P9 pauses for an approved validation matrix; P11 records and reports the current P95 baseline before performance changes; P12 requires P1–P11 completion and provider evidence.

---

## 6. Frontend Migration Plan

1. **P1:** tests + footer count fix only; no UX change.
2. **P7 step 1 (non-breaking):** consume capability payload defensively. Missing metadata enters an explicit legacy mode containing only combinations the current backend is known to accept; it never means all future combinations are enabled.
3. **P7 step 2:** universe selector + per-market state retention + result tagging; store shape versioned (`scanMeta.market` preferred over `activeMarket` in all copy).
4. **P7 step 3:** consume backend-authoritative feature series/values for charts and cards, or retain client calculations only after versioned golden equivalence tests (F-016).
5. **P10:** capability-gated Detect Patterns; rename misleading TA-Lib presentation to the actual custom deterministic detector while retaining deprecated wire aliases.
6. **Continuous:** FilterPanel remains fully data-driven — no strategy names hardcoded client-side (already true today, preserve it; `CATEGORY_LABELS` fallback at `FilterPanel.jsx:153` already tolerates unknown categories).

## 7. Backend Migration Plan

1. Additive-first: new packages (`domain/`, `providers/`, `strategies/`, universe providers) land alongside old code; old entry points (`get_flat_filters`, `canonicalize_symbol`, `CRYPTO_SYMBOLS` fallback) become shims.
2. P5 owns the additive universe-schema/backfill migration; rebuild universe immediately after deploy and coordinate scheduler markers (`universe:refresh_scheduled` Redis key, `universe_builder.py:20`). If and only if the approved P8 provider source requires rolling observation storage not expressible in P5's generic schema, P8 may add a narrowly scoped additive migration documented with the provider-source decision.
3. Shim removal only in P12 after equivalence and integration tests pass.
4. Worker compatibility: RQ job signature `run_scan_job(job_id, user_id, market, filters, timeframe, limit)` (`worker.py:1-4`) gains `universe=None` keyword-last so in-flight jobs from the previous release still execute during rolling deploys.
5. Typed context/error fields are additive; legacy matched `results` remain while `symbol_outcomes` and structured failure states roll out. Persistence failures are never swallowed as successful scans (F-020).

## 8. Testing Strategy

- **Characterization (P1):** pin crypto scan, health/live-vs-fallback counts, zero/indicator divergence, permissive request behavior, NASDAQ starvation, empty-universe publication/fallback, insufficiency/provider classification, persistence failure, and worker error serialization.
- **Unit:** per-strategy equivalence + capability tests including RSI Overbought/Oversold (P4); domain symbol/context round-trips (P2); approved lookback/session/partial-candle math and resampling goldens (P6); signal-resolver rename aliases (P10).
- **Contract:** `FakeProvider` implements the full protocol; a shared contract-test suite runs against both `FakeProvider` and (optionally, keyed) `PolygonProvider` (P3).
- **Integration:** scan request → persisted rows → status payload for (market × universe × timeframe) samples; include structured failure/persistence paths and `scan_templates.evaluate_template`, which bypasses the queue and calls `scan_market` directly.
- **Frontend:** store tests for payload/context construction including `universe`; stale-market response tests; component tests for capability-disabled controls, insufficiency/errors, and authoritative indicator values; e2e per P12.
- **Cross-asset (P9):** parameterized strategy matrix on golden fixtures only after the matrix/drift proposal is approved.
- **Performance/resilience (P11):** reproducible current P95 baseline, repeated/cached P95 target, cancellation, DB-session isolation, fair deterministic results, cache freshness, universe degradation, and persistence failure.
- **Coverage gate:** keep the existing `--cov-fail-under=70` CI bar; new packages target ≥85 %.

## 9. Compatibility Strategy

- Wire values `stocks`/`crypto`, canonical timeframe strings, and all existing filter keys are frozen (ADR-1).
- All new request fields optional with behavior-preserving defaults (`universe`, strategy params, pattern `market`).
- All new response fields additive (`symbol_outcomes`, `insufficient_data_symbols`, capability blocks, timing/error meta); aliases named `talib_*` for the existing custom deterministic analysis are retained for one release but new labels state the actual implementation.
- DB: additive columns + constraint replacement with backfill; `ScanResult`/`ScanHistory` untouched except optional new nullable columns if per-strategy signals are persisted (decision deferred to P6).
- Saved templates: pre-migration audit query for unknown filter keys before strict validation ships (P4 risk item).

## 10. Data-Provider Validation Tasks

Each task records: endpoint, plan response, sanitized sample payload, observation date, and capability decision. All are prerequisites for the phases noted. Every item is currently `Requires external provider verification` (review §17 and §21 item 1). The initial credential smoke check succeeded on 2026-07-12 (`GET /v3/reference/tickers/AAPL`, HTTP 200); it proves authentication only, not any V-1–V-8 capability.

| # | Verify | Blocks |
|---|---|---|
| V-1 | Intraday history depth per span (1m–4H) for stocks on the current plan; confirm `data_limit_notice` thresholds match reality | P6 lookbacks |
| V-2 | `45m` (multiplier=45/minute) and `timespan=year` aggregates return usable bars for stocks | P6 resampling decision; review §14 stock-provider `Unverified` cells |
| V-3 | Crypto aggregates entitlement: spans, history depth, `X:` symbol coverage for the target pair set | P8; review §14 crypto-provider `Unverified` cells |
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
| Universe migration publishes empty/stale data or breaks weekly rebuild | P5/P11 | Medium | High | Candidate validation, last-known-good preservation, backfill/rebuild rehearsal, Postgres constraint tests, degraded-state metrics |
| `insufficient_data` semantics confuse users (fewer/more matches) | P6 | Medium | Medium | Additive meta first, UI explanation in P7, release notes |
| Worker concurrency corrupts DB sessions, breaks cancel, or reintroduces exchange bias | P11 | Medium | High | Persist on coordinator thread only; cancellation/fairness tests; keep sequential mode behind env flag |
| Rolling deploy with changed job signature | P5/P7 | Low | Medium | Keyword-last optional args; workers deploy before web |
| YOLO gating perceived as feature regression by crypto users | P10 | Low | Low | Clear UI message + documented enablement path |
| Capability payload drift between validation and UI | P4/P7 | Low | Medium | Single registry source; contract test asserting payload ⊇ validator rules |
| Browser and backend indicators continue to disagree | P4/P7/P9 | Medium | High | One authoritative feature path or versioned cross-language golden equivalence, including valid zero values |
| Persistence or provider failures appear as no matches | P3/P6/P11 | Medium | High | Typed failures, full logging/context, status/UI propagation, boundary tests; no silent empty-success handlers |

## 12. Prioritized Backlog

1. **P1** characterization, live counts, and D-001–D-005 reconciliation (F-010/F-011/F-013/F-016–F-020).
2. **P2** canonical asset/instrument/timeframe/request-context models (F-014/F-017).
3. **P3** provider seam and typed provider failures (F-009/F-020).
4. **P4** strategy/feature/capability registry and specified RSI strategy (F-003–F-005/F-012/F-015–F-017).
5. **P5** safe/fair generalized universes and request selection (F-001/F-006/F-018/F-019).
6. **P6** confirmed timeframe/data-quality rules and explicit outcomes (F-004/F-008/F-015/F-020).
7. **P7** capability-driven frontend, immutable context, and authoritative indicators (F-002/F-005/F-015–F-017).
8. **P8** approved-source 100+ pair/90-day crypto universe (F-001/F-014).
9. **P9** approved cross-asset validation matrix (F-004/F-010/F-016).
10. **P10** detector gating and truthful custom-deterministic naming (F-007).
11. **P11** baseline-driven performance, fairness, observability, and resilience (F-009/F-011/F-012/F-018–F-020).
12. **P12** final acceptance and finding/matrix disposition.

## 13. Overall Definition of Done

A normal user, through the supported frontend, can:

1. Choose equities or cryptocurrencies (existing toggle, preserved).
2. Choose an applicable market/universe: All US / NASDAQ / NYSE / Crypto top-USD-pairs (P5, P7, P8).
3. Choose an applicable timeframe, with plan-unavailable intervals visibly disabled (P4/P6/P7, resolving D-001).
4. Choose one or more supported strategies, with unsupported asset/timeframe combinations disabled and explained (P4, P7).
5. Start a scan (existing flow, preserved).
6. Retrieve correct market data with computed lookbacks and per-class calendars (P6, P8).
7. Execute strategies with **no asset-specific orchestration branches** — `scan_market` contains no `market ==` conditionals; universe registry and strategy capabilities absorb the variation (P4, P5; today's single branch at `scans.py:336` removed).
8. Receive bullish, bearish, neutral, **or insufficient-data** results per symbol (P4, P6).
9. View correctly labeled results and charts, tagged with the market/universe/timeframe they came from (P7).
10. Receive a clear validation message for unsupported combinations (P4, P7, P10).

Automated tests demonstrate: asset-class/context and timeframe survive the full request path; strategies declare and enforce capabilities; the specified RSI registry extension requires no orchestration edit; equity and crypto universes share one safe/fair contract; provider details do not leak into strategy code; valid zero indicators are preserved and chart/card values agree with the authoritative feature path; unknown context/strategies reject explicitly; unsupported YOLOv8 usage is rejected; frontend controls expose only valid combinations; crypto initiates through the normal frontend; empty universe builds retain last-known-good state; NASDAQ/NYSE cannot be starved by result caps; and provider/persistence failures remain distinguishable from valid empty/no-signal/insufficient outcomes.

## 14. Recommended Implementation Order

**P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8 → P9 → P10 → P11 → P12.**

This order is authoritative and dependency-gated. There are no sanctioned partial starts, overlaps, or reorderings. Done means all Section 13 items are verified, every review §14 `Unverified` cell is regraded with evidence and enforcement, and every finding F-001–F-020 meets the completion criterion in Section 2 or has an explicitly approved deferral.
