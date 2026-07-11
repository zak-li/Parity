# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Inbound request guards**: per-client token-bucket rate limit (`429`),
  concurrency cap (`503`), and request timeout (`504`), configurable via
  `XI_API_*` variables.
- **Observability**: `X-Request-ID` propagation, structured JSON logs, and a
  Prometheus `GET /metrics` endpoint.
- **Fallback FX provider** with a per-provider circuit breaker behind the
  `FxDataProvider` port.
- **Docker**: non-root image with healthcheck, `docker-compose` (API +
  PostgreSQL), and a GHCR publish workflow.
- **Alembic migrations** for the PostgreSQL schema; `create_all` is now gated
  behind `XI_DB_AUTO_CREATE`.
- `docs/MODELS.md` documenting model assumptions, limits, and numerical
  validation; docstrings on the key quantitative functions.
- CycloneDX SBOM artifact in the security workflow.

### Changed
- `GET /health` no longer exposes the package version (fingerprinting).
- `Strict-Transport-Security` added to the security headers.
- Package version is now single-sourced from the installed metadata.

## [0.7.0] - 2026-07-04

### Added
- **Portfolio risk attribution**: per-currency component/marginal CVaR (Euler
  allocation) exposing each currency's share of the tail shortfall
  (`POST /api/v1/portfolio/simulations`).
- **Expected Shortfall backtest** (Acerbi-Szekely Test 2) with a Monte-Carlo null
  distribution, complementing the Kupiec VaR test
  (`POST /api/v1/backtests/es`).
- **Closed-form FX option Greeks** (Garman-Kohlhagen delta, gamma, vega, theta,
  domestic/foreign rho) (`POST /api/v1/hedge/greeks`).
- **Cashflow ladder**: multi-date exposure simulated from one shared Brownian
  path with layered per-tranche forward hedging
  (`POST /api/v1/ladder/simulations`).
- Advanced CI/CD and quality gates: `ruff` lint + format, `mypy` type checking,
  a 90% coverage gate, packaged build verification, **CodeQL** analysis,
  dependency review, `pip-audit`, **Dependabot**, and automated GitHub Releases
  on `v*` tags.

### Fixed
- Date-fragile API test fixture that failed on non-business days; the FX series
  is now anchored to a fixed business day instead of `date.today()`.

## [0.6.1] - 2026-07-03

### Fixed

- **GARCH volatility estimator systematically overstated volatility by 2×–5×.**
  On well-behaved series the SLSQP optimizer stayed pinned at its initial guess
  (`omega = 0.1 × var`, `alpha = 0.08`, `beta = 0.90`), which implies a long-run
  variance of 5× the sample variance. The estimator now uses **variance
  targeting** — `omega` is constrained so the long-run variance equals the
  empirical variance and only `(alpha, beta)` are optimized — recovering the true
  sigma to within a few percent. Added a regression test that checks recovery of
  a known sigma across seeds.

## [0.6.0] - 2026-07-03

### Added

- **Simulation core.** Delivery-date exchange-rate pricing under a risk-neutral
  `GBM` respecting covered interest rate parity, with optional `Heston`
  stochastic volatility, `Student-t` fat tails, and `Merton` jumps, sampled with
  `Sobol` sequences and antithetic variates.
- **Volatility and correlation estimation.** `historical`, `EWMA`, and
  `GARCH(1,1)` estimators with automatic fallback, plus dynamic `DCC-GARCH`
  portfolio correlations.
- **Risk metrics.** Margin distribution percentiles, loss probability, Expected
  Shortfall (`CVaR`), and the 0–100 **Vulnerability Score**.
- **Hedging engine.** `CVaR`-optimal hedge ratio and comparison of the unhedged
  position against a forward, an option, and a collar, priced with
  `Garman-Kohlhagen` or smile-consistent `Monte Carlo` under Heston.
- **Portfolio aggregation.** Per-currency netting, correlated simulation,
  portfolio `VaR`/`CVaR`, and diversification benefit for multi-currency orders.
- **Governance.** `Kupiec` VaR backtesting, deterministic and historical
  (`2008`, `COVID-19`) stress tests with a reverse stress test, and a versioned
  Office des Changes eligibility rules engine.
- **Monitoring.** Inter-run monitor with typed alerts dispatched to console,
  webhook, or email sinks.
- **API.** Hardened `FastAPI` service with API-key authentication, anti-`SSRF`
  host allowlist, token-bucket rate limiting, and security headers.
- **Persistence.** In-memory, `PostgreSQL`, `MongoDB`, and `Neo4j` repositories
  behind a composite adapter.
- **AI narrative.** Optional `Groq` narrative generation (import-guarded).
- **Tooling.** Test suite (361 tests) and GitHub Actions CI on Python 3.11/3.12.

[Unreleased]: https://github.com/zak-li/Parity/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/zak-li/Parity/compare/v0.6.1...v0.7.0
[0.6.1]: https://github.com/zak-li/Parity/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/zak-li/Parity/releases/tag/v0.6.0
