# Market Scanner Pro — Improvement & Continuation Plan

> Priorities reflect the code and dependency state reviewed on 21 June 2026. This is a plan only; no application source was modified as part of the onboarding review.

## 1. Critical issues — fix immediately

| Priority | Issue and evidence | Recommended remediation | Expected result |
|---|---|---|---|
| P0 | A default administrator (`admin@marketscanner.local` / `admin123`) is created at startup and the password is documented in the README. | Remove automatic production credential creation. Use an explicit one-time bootstrap command that requires a generated password; rotate the local admin and any exposed credentials. | No universally known admin account. |
| P0 | `backend/.env` with `POLYGON_API_KEY`, `DATABASE_URL`, and `SECRET_KEY` exists, while the project has no local `.gitignore` and no reliable project Git boundary. | Treat the values as potentially exposed: rotate them, create a redacted `.env.example`, add a project-level `.gitignore`, and move production secrets to a secret manager/deployment configuration. | Credentials are not retained in source, builds, or backups. |
| P0 | `app.py` starts Flask with `debug=True`; CORS permits `*` on every API route. | Make environment-specific configuration via an app factory. Disable debug outside local development; allow only known frontend origins; add security headers and structured error responses. | No debugger exposure; browsers from arbitrary origins cannot call the API. |
| P0 | Login/register save `auth_token`, but Axios reads `access_token`. No bearer token is sent, so protected watchlist/admin actions fail. The 401 handler redirects to nonexistent `/login`. | Define one token key and one auth lifecycle. Fix interceptor and cleanup code; use application navigation/modal on 401; add integration tests for register/login/me/watchlist/admin. | Authentication works end-to-end and fails gracefully. |
| P0 | `AdminPanel` calls nonexistent `adminAPI.getScanHistory`; client exposes `getScans`. The first `Promise.all` therefore fails and hides all admin data. | Rename the call or export an alias; remove the unsupported `deleteUser` client function or add a reviewed endpoint. Surface load errors in the panel. | Admin panel loads reliably. |
| P0 | Public scan/news/fundamentals/detail endpoints can cause external provider calls. Scans run synchronously for up to the fixed universe, block a Flask worker, and have no request-level abuse protection. | Add per-IP/user rate limits, input schemas and bounds, provider-budget protection, and asynchronous scan jobs. Restrict expensive features by authenticated plan if required. | API quota and server capacity are protected. |
| P0 | `npm audit --package-lock-only` reports 25 vulnerabilities: 4 high, 17 moderate, 4 low. Direct locked dependencies include Axios 1.13.5, Vite 6.4.1, and PostCSS 8.5.6. | Upgrade, regenerate lockfile, and re-run audit. At minimum move Axios to a release at or above the audit's 1.16.0 remediation threshold; Vite to a release above 6.4.2; PostCSS to 8.5.10 or newer. Validate Vite/plugin compatibility and record the audit in CI. | Removes reported direct high-risk paths and brings the toolchain current. |

### Audit detail

The current audit identifies high-severity paths through:

- `axios@1.13.5`: multiple SSRF/proxy bypass, prototype-pollution, header injection, resource-exhaustion, and credential-leak advisories; the audit includes fixes requiring versions up to `>=1.16.0`.
- `vite@6.4.1`: dev-server arbitrary-file-read/path traversal and Windows alternate-path/UNC-related advisories affecting versions through 6.4.2 in the audit ranges.
- Transitive `picomatch@2.3.1`: ReDoS/method-injection advisories.
- Transitive `form-data@4.0.5`: multipart CRLF injection advisory.

`postcss@8.5.6`, `@babel/core@7.29.0`, `follow-redirects@1.15.11`, Tailwind's file-watching chain, and several transitive packages also have low/moderate findings. Python packages were not audited with `pip-audit` because it is not installed; add it to the first remediation sprint rather than inferring a clean Python dependency set.

## 2. Architecture and code quality

### Refactor targets

| Problem | Why it matters | Target design |
|---|---|---|
| `backend/app.py` is a 2,641-line monolith. | Configuration, data models, auth, provider transport, indicator math, news, fundamentals, and HTTP routes change for different reasons and cannot be tested independently. | Create `create_app(config)` plus modules for `models`, `auth`, `clients/polygon`, `services/{technical,news,fundamentals,scans}`, `api` blueprints, schemas, and error handlers. Keep routes thin. |
| Two incompatible scanner implementations coexist. | The inactive one imports missing modules and uses a different data model/JWT system, creating confusion and accidental failure risk. | Delete it after preserving useful behavior, or explicitly migrate it to the active architecture. Do not leave broken code on the import path. |
| Global memory holds tokens, cache, and rate-limit state. | It breaks across restart/workers, cannot revoke reliably, leaks memory without bounded cleanup, and makes Gunicorn scaling unsafe. | Persist sessions/revocations in a database or use signed JWT access/refresh tokens with rotation; move cache/rate limiting/job state to Redis or equivalent. |
| Schema creation is implicit and has no migrations. | Production schema changes cannot be audited, rolled forward/back, or safely deployed. | Add Flask-Migrate/Alembic, initial migration, DB constraints/indexes, and an explicit seeded-development command. |
| Client pages are in one component with state-only navigation. | No deep links, refresh persistence, route guards, or error boundaries. | Introduce React Router with protected/admin routes and route-level lazy loading. |
| API DTOs are ad hoc nested dictionaries. | Contract drift already caused runtime defects. | Define request/response schemas (Pydantic/Marshmallow/OpenAPI on backend) and generate or share typed client contracts. Migrate frontend gradually to TypeScript. |

### Duplication and cleanup

- Centralize timeframe availability. The frontend, `/api/filters`, and `TIMEFRAME_MAP` disagree about `4H` and available paid intervals.
- Centralize symbol identity as `{ providerSymbol, displaySymbol, market }`. Do not strip `X:` before a future provider call. This fixes crypto detail/watchlist timeframe behavior.
- Define a common API-error mapper and remove scattered `console.error`-only paths. Users need visible errors, operators need structured logs/correlation ids.
- Treat price/statistical calculations as domain functions with fixtures. The frontend should either display backend indicator series or intentionally document the distinct visual formulas.
- Validate model enums (`role`, `plan`, market, timeframe) and use database constraints/unique indexes rather than only ad hoc route logic.

## 3. Performance and reliability

| Opportunity | Current behavior | Implementation note |
|---|---|---|
| Asynchronous scans | One Flask request sleeps between Polygon calls and can take many minutes. | Submit a scan job, queue tasks (RQ/Celery/Arq), persist job/status/results, poll or use SSE/WebSocket for real progress/cancellation. |
| Provider fetch efficiency | Full scans fetch OHLCV per symbol; snapshots are implemented but unused. | Use supported batch/snapshot APIs for coarse filtering, then fetch historical bars only for candidates; cache provider responses with provider-aware keys. |
| Correct caching | All cache entries effectively expire after five minutes because `cache_get` ignores entry TTL. | Read `entry['ttl']`, add cache size/bounded eviction, and cache negative/error outcomes cautiously. Use shared cache for multiworker deployment. |
| Reliability around provider failures | 429 retry is recursive; malformed request parameters can 500; no retry policy for transient upstream failures. | Add validated schemas, iterative bounded retry/backoff/jitter, upstream timeout/error mapping, circuit breakers, and request IDs. |
| Database access | Scans persist individual rows and global history with minimal indexes. | Batch inserts, add indexes for common admin/history queries, retention policy, ownership linkage, and pagination. |
| Frontend bundle | Production JS is 490.30 kB / 147.59 kB gzip; all feature pages ship eagerly. | Lazy-load modal/chart, admin, newsroom, and fundamentals routes; inspect bundle; use route-level Suspense. |
| Chart lifecycle | Chart is recreated when parent passes a new indicators object. | Memoize stable data/options or use targeted series updates. Prefer `ResizeObserver` to a global resize listener. |
| Search/fetch cancellation | 300ms debounce does not cancel in-flight requests. | Use `AbortController`/Axios signal and ignore stale responses; cache recent search queries. |

## 4. Feature completion inventory

| Feature | What exists | What remains / recommended completion |
|---|---|---|
| Authentication | Register, login, me, password change endpoint, modal. | Repair token contract; add password-change UI, password recovery/verification as required, session logout/revocation, stronger password policy and rate limiting. |
| Admin management | Backend listing/update/stats/history and UI tables. | Fix method-name failure; validate changes; define user deletion policy rather than dangling client method; audit admin actions. |
| Watchlist | Per-user add/list/remove and UI. | Preserve canonical crypto symbol; show/edit `notes`; market data/alerts; database uniqueness constraint; toasts/errors. |
| Scan progress | Scanner and static loading UI. | Introduce background jobs, real progress, cancel/retry/history detail, and explicit AND/OR match-mode selection. |
| Timeframes | Multiple configured keys and paid-plan messaging. | Implement or remove `4H`; disable unsupported choices rather than invoking an error; consolidate backend/frontend availability. |
| News aggregation | Multi-source design, normalization, filtering, sentiment display. | Add `feedparser` and optional model extras or present sources as unavailable; verify provider licensing; improve dedupe and source-specific rate limits; validate `limit`/`days`. |
| FinBERT | Runtime attempt and lexicon fallback. | Make it an optional, documented extra/container image; warm model separately; batch inference; expose method/caveat. |
| Fundamentals | Rich Polygon-derived dashboard. | Validate financial-statement field semantics, account for fiscal periods/negative values, show data freshness, and add filing/source links. Limit feature to supported equity symbols. |
| Chart API | `/api/chart` endpoint exists. | Either use it for progressive chart loading or remove it; align it with paid-timeframe rejection rules. |
| Legacy scanner | Blueprint/service prototype exists. | Reconcile or delete; currently it is unusable due to missing imports/dependencies/model fields. |

## 5. High-value product roadmap

| Feature | Description and technical approach | Complexity | Priority |
|---|---|---|---|
| Saved scans, alerts, and notifications | Persist user-owned scan criteria/results; schedule background evaluations; notify only after explicit opt-in and deduplicate alert events. | High | P1 |
| Real scan-job experience | Queue scans, show symbol-by-symbol progress, cancellation, errors, prior runs, provider usage, and result comparison. | High | P1 |
| Watchlist dashboard | Canonical symbols, latest quote/technical signal, note tags, sorting, and price/indicator threshold alerts. | Medium | P1 |
| Strategy evaluation/backtesting | Let users run a named, versioned filter strategy against historical data; report assumptions, sample period, drawdown, win rate, and limitations. Never present it as financial advice. | High | P2 |
| Portfolio/research journal | Optional manual holdings, thesis/notes, entry/exit records, and performance visualizations without executing trades. | Medium | P2 |

Each feature depends on the security, user-ownership, provider-entitlement, and background-job foundations above. Avoid adding broker connectivity until those controls and compliance requirements are defined.

## 6. Developer experience and tooling

| Area | Recommendation |
|---|---|
| JavaScript quality | Add ESLint (React hooks/accessibility), Prettier, import ordering, `lint`/`format:check` scripts, and lint-staged/Husky or equivalent pre-commit hooks. |
| Python quality | Add Ruff (lint/format), pyright or mypy where valuable, pytest, coverage, and `pip-audit`. Pin transitive dependencies with a lock/constraints workflow. |
| Testing | Backend unit tests for indicators/filter semantics/cache/auth; Flask API tests with a disposable database and mocked Polygon; React Testing Library for store/components; Playwright/Cypress for register-login-watchlist-admin and scan flows. |
| CI | On every PR: install from locks, lint, test, build, `npm audit`, `pip-audit`, secret scan, dependency review, and coverage threshold/report. Add scheduled dependency updates. |
| Operations | App factory/config profiles, Docker Compose for frontend/API/Postgres/Redis, health/readiness endpoints, structured JSON logs, exception tracking, metrics, and documented backups/migrations. |
| Documentation | Replace setup assumptions with a tested bootstrap path; add `.env.example`, API/OpenAPI reference, architecture decision records, provider entitlement matrix, data/financial-disclaimer policy, and runbooks for seed/migration/credential rotation. |

## 7. Execution roadmap

### Sprint 0 — Security and broken user journeys (1–3 days)

Goals: make the existing app safe to run in a controlled environment and restore core authenticated paths.

- Rotate `.env` secrets and default admin credentials; create `.env.example` and `.gitignore`; establish a project repository boundary.
- Remove production default-admin creation and debugger; restrict CORS/origins.
- Repair auth storage/interceptor/401 behavior, admin API call, and unsupported admin delete client call.
- Upgrade audited frontend dependencies, regenerate lockfile, run audit again; add `pip-audit` and audit Python dependencies.
- Add request validation/bounds for auth, scan, news, and admin update inputs.

Expected outcome: no known default credentials, corrected protected-route behavior, a materially safer API perimeter, and a clean-or-explained dependency audit baseline.

### Sprint 1 — Backend foundation and scan reliability (1–2 weeks)

Goals: make data/provider behavior testable and suitable for deployment.

- Introduce app factory, configuration profiles, blueprints, error handling, service boundaries, and structured logs.
- Remove or migrate the orphaned scanner implementation.
- Add Alembic migrations, constraints/indexes, development seed command, and a PostgreSQL/Redis deployment path.
- Replace process-local token/cache/rate-limit assumptions with durable/shared components.
- Build asynchronous scan jobs with real progress, retries, provider quotas, cancellation, and persisted user ownership.
- Correct TTL use, bounded caching, provider retry/backoff, input schemas, and canonical crypto symbols.

Expected outcome: horizontally safe services, traceable scan jobs, correct cache behavior, and a maintainable backend boundary.

### Sprint 2 — Quality, tests, and frontend experience (1–2 weeks)

Goals: prevent contract regressions and improve perceived performance.

- Add API contract tests, technical-analysis fixtures, auth/watchlist/admin integration tests, component tests, and two or three end-to-end critical flows.
- Add lint/format/typecheck/test scripts, CI, secret scanning, audit gates, and coverage targets.
- Add React Router/protected routes, API error states, crypto symbol preservation, disabled unsupported timeframes, and real job progress UI.
- Lazy-load heavy pages/chart and inspect bundle improvements; cancel stale search requests.
- Complete admin error handling and watchlist notes/feedback.

Expected outcome: automated confidence for critical paths, a lower-risk release pipeline, and a responsive UI that explains unsupported states.

### Sprint 3+ — Product depth (ongoing)

Goals: turn analysis screens into a reliable user research workflow.

- Ship saved scans/alerts and a richer watchlist on the job/notification foundation.
- Decide and implement RSS/FinBERT optional dependencies with licensing, operational budgets, and explicit source availability.
- Improve fundamentals provenance/freshness and provide historical strategy evaluation with clear methodology.
- Integrate the YOLOv8 pattern-detection service and `/api/patterns/detect` endpoint.
- Wire the frontend signal badge and bounding-box overlay to the new pattern-detection endpoint.
- Add a `pip-audit` CI check for `ultralytics` and `opencv-python`.
- Store pattern-detection logs (annotated screenshots and Excel reports) in `logs/pattern_detections/`, scoped to the owning user.
- Establish observability, backups, retention, data-provider usage dashboards, accessibility review, and a regular dependency-maintenance cadence.

Expected outcome: differentiated market-research features that are measurable, supportable, and appropriately caveated.

---

### New Feature — Real-Time Chart Pattern Detection (YOLOv8s + TA-Lib)

#### Overview

Integrate the Hugging Face model `foduucom/stockmarket-pattern-detection-yolov8`
as the primary signal source for chart pattern analysis.

Deployment model: this is a web application. Screen capture happens in the
client browser, not on the server. The frontend captures or crops the chart
canvas using the browser Canvas API, `html2canvas`, or the existing chart canvas
reference, then posts the chart image to `/api/patterns/detect` as base64. The
backend decodes that payload into an OpenCV Mat/NumPy image array and runs
inference; it must not perform server-side screen capture.

#### Model Details

- Source: https://huggingface.co/foduucom/stockmarket-pattern-detection-yolov8
- Model file: `model.pt` (88.4 MB)
- Detects: Head & Shoulders Top/Bottom, M-Head, W-Bottom, Triangle, StockLine
- Input: Client-captured chart image sent to `/api/patterns/detect` as base64
  or file upload, decoded by the backend into an OpenCV Mat/NumPy image array
- Required packages: `ultralytics==8.3.94`, `opencv-python==4.11.0.86`,
  `numpy`, `openpyxl==3.1.5`

#### Signal Priority (Strict Order)

The system must resolve and display pattern signals using the following priority:

| Priority | Source | Condition |
|----------|--------|-----------|
| 1 (Highest) | YOLOv8s + TA-Lib | Both sources detect the same/confirming pattern |
| 2 | YOLOv8s only | YOLOv8s detects a pattern; TA-Lib is absent or inconclusive |

> TA-Lib results alone (without YOLOv8s confirmation) must NOT be surfaced
> as primary signals. They serve only as a confirmation layer.

#### Implementation Tasks

1. Download `model.pt` from the Hugging Face repo and store under `models/yolov8/`.
2. Create `services/patternDetection/yoloService.py` in the Python backend:
   - Accept a decoded image buffer as an OpenCV Mat/NumPy image array.
   - Keep the service limited to image-array inference; no server-side screen capture belongs here.
   - Run inference via `ultralytics` YOLO.
   - Return detected patterns with confidence scores and bounding boxes.
3. Create `services/patternDetection/signalResolver.py` in the Python backend:
   - Accept YOLOv8s output and TA-Lib output as inputs.
   - Apply priority logic (table above) to emit a single resolved signal.
   - Require a minimum YOLOv8 confidence before emitting a signal (default: `0.50`).
   - If YOLOv8 confidence is below the threshold, suppress the signal entirely; do not fall back to TA-Lib alone.
   - If YOLOv8 detects pattern A and TA-Lib confirms pattern B, emit Priority 2 (`YOLOv8` only) and include `talib_conflict: true` in the response.
4. **Task 3b — Create `/api/patterns/detect` endpoint (Python/Flask):**
   - Accept a client-captured chart image supplied as base64 or a file upload.
   - Decode the uploaded image into an OpenCV Mat/NumPy image array before calling `yoloService.py`.
   - Trigger YOLOv8 inference, TA-Lib confirmation, and `signalResolver`.
   - Return JSON containing `{ signal_priority, pattern, confidence, source_badge, bounding_boxes, talib_confirmation, talib_conflict }`.
   - Apply the same rate-limiting and authentication guards as `/api/scan`.
5. Update the UI to display:
   - Capture the chart region using `html2canvas` or the existing chart canvas reference, then POST the base64 image to `/api/patterns/detect`.
   - Pattern label and confidence score.
   - Signal source badge: `YOLOv8 + TA-Lib` or `YOLOv8`.
   - Bounding box overlay on the captured chart image.
6. Add output logging: annotated screenshots + Excel report (labels + timestamps),
   scoped to the owning user and stored in `logs/pattern_detections/`, following the structure in `main.py` of the Hugging Face repo.

#### Complexity: High
#### Priority: High
