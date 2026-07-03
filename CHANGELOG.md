# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/zak-li/Parity/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/zak-li/Parity/releases/tag/v0.6.0
