# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] (2026-08-20)

### Added
- Rebrand official package identifier to `Parity` with full dual-import support (`import Parity`, `import parity`, and `import sdk`).
- Add HMAC-SHA256 commercial API key verification guard in `core/licensing.py` with graceful open development mode tolerance.
- Harden REST API service with production security headers (HSTS, CSP, X-Frame-Options) and default documentation endpoint protection.
- Restructure project tooling under `scripts/` into benchmark, backtesting, and DevOps suites with complete documentation.

### Security
- Enforce strict commercial API license validation across quantitative calculation engines.

## [0.9.2] (2026-08-18)

### Security
- Enforce multi-tenant isolation for persisted simulations, scoping every run to the authenticated client (`client_id`) and filtering simulation history, direct lookups, and change alerts by tenant. Adds a `client_id` column (migration `0003`) across in-memory, PostgreSQL, and MongoDB repositories.
- Fail closed on a missing API-key pepper when `XI_ENV=production` rather than falling back to an insecure development pepper.

### Added
- Add command-line interface executable (`core/cli.py`) with support for `score`, `portfolio`, and `backtest` subcommands.
- Integrate ExchangeRate-API provider (`core/io/fx/exchangerate_api.py`) with support for API-key authenticated live FX rates.
- Unify FX provider resolution in `core/io/fx/factory.py` to seamlessly route between Frankfurter, ExchangeRate-API, and static providers.
- Implement formal Expected Shortfall and Kupiec POF statistical backtesting validation in `core/models/backtesting.py`.
- Introduce `XI_DB_STRICT` environment flag to turn database connection failures into explicit startup errors instead of silent in-memory fallback.
- Add `XI_ENV` deployment environment configuration toggle (`development` by default, `production`).
- Add automated PyPI package publishing workflow in `.github/workflows/pypi-publish.yml`.

### Changed
- Update brand banner graphics to responsive vector SVG with automated dark and light mode theme support.

## [0.9.1] (2026-07-24)

### Added
- Add administrative REST endpoints (`POST/GET/DELETE /api/v1/keys`) and auth repository methods to mint, list, and revoke per-client API keys.
- Add client identity endpoint (`GET /api/v1/me`) returning current authenticated client details.
- Include standard rate-limit headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`) on `429` responses alongside `Retry-After`.

### Fixed
- Re-align connector ETL routes under `/api/v1/connectors/...` to match documented API namespaces.

## [0.9.0] (2026-07-20)

### Security
- Enable Row Level Security (RLS) on all public Supabase tables in `scripts/ops/supabase_rls_fix.sql`, closing PostgREST exposure while preserving owner access.

### Added
- Introduce Auth0 SSO browser-SPA authentication supporting RS256 Bearer tokens with audience, issuer, and authorized party validation alongside developer API keys.
- Add configurable cross-origin resource sharing (CORS) support for web frontends on FastAPI service using `XI_CORS_ALLOW_ORIGINS`.
- Integrate asynchronous MLflow experiment tracking in `core/app/tracking.py` for automated background recording of simulation parameters, metrics, and models.
- Support distributed high-volume batch simulations across Apache Spark worker nodes in `core/app/distributed.py`.
- Provide full backend orchestration in `docker-compose.yml` combining FastAPI, Redis, MLflow tracking server, and Spark standalone cluster.
- Add automated remote host deployment script in `scripts/ops/deploy_vm.sh`.

### Fixed
- Correct Redis connection and rate-limiter resolution logic by replacing falsy length evaluation with strict non-null checks.

## [0.8.0] (2026-07-18)

### Added
- Implement inbound request guards in `api/guards.py` providing per-client token-bucket rate limiting (`429`), concurrency limits (`503`), and request timeouts (`504`) configured with `XI_API_*` environment variables.
- Add structured observability features in `api/observability.py` including `X-Request-ID` tracing, JSON logging, and Prometheus metrics through `GET /metrics`.
- Implement resilient fallback FX provider in `core/io/fx/fallback.py` with per-provider circuit breakers.
- Provide non-root production container configuration with automated health checks and multi-service orchestration.
- Set up PostgreSQL schema migration tracking with Alembic and `XI_DB_AUTO_CREATE` toggle.
- Document mathematical formulations, boundary conditions, and numerical validation reference in `docs/MODELS.md`.
- Generate CycloneDX Software Bill of Materials (SBOM) in the automated security pipeline.

### Changed
- Remove internal package version disclosure from `GET /health` to prevent reconnaissance.
- Add strict security headers including Strict-Transport-Security (HSTS), Content-Security-Policy (CSP), and anti-MIME-sniffing protections.
- Streamline package version resolution directly from installed metadata.

### Dependencies
- Upgrade core dependencies including `redis` (8.x), `cryptography` (49.x), `PyJWT` (2.13.x), `fastapi` (0.139.x), `ruff` (0.15.x), and `mypy` (2.3.x).
- Relax development build dependency constraint to `>=1.5.0`.

## [0.7.0] (2026-07-04)

### Added
- Implement portfolio risk attribution in `POST /api/v1/portfolio/simulations` with per-currency component and marginal CVaR Euler allocation.
- Add Expected Shortfall backtesting in `POST /api/v1/backtests/es` using Acerbi-Szekely Test 2 with Monte Carlo null distribution.
- Calculate analytical closed-form Garman-Kohlhagen Option Greeks (Delta, Gamma, Vega, Theta, Domestic Rho, and Foreign Rho) in `POST /api/v1/hedge/greeks`.
- Simulate multi-horizon cashflow ladders with correlated currency tranches and layered forward hedging in `POST /api/v1/ladder/simulations`.
- Establish automated CI/CD quality gates for Ruff linting, Mypy type checks, 90% test coverage enforcement, CodeQL analysis, and release packaging.

### Fixed
- Anchor FX test fixtures to fixed business dates rather than dynamic system dates to ensure deterministic CI runs.

## [0.6.1] (2026-07-03)

### Fixed
- Stabilize SLSQP optimizer long-run variance estimation in GARCH models using empirical variance targeting, recovering true volatility parameters within 1%.

## [0.6.0] (2026-07-03)

### Added
- Implement core quantitative simulation models including risk-neutral GBM pricing under CIP, Heston stochastic volatility, Student-$t$ distributions, Merton jump diffusion, and Sobol quasi-random sampling.
- Provide volatility and correlation estimators including Historical, EWMA, GARCH(1,1), and dynamic DCC-GARCH portfolio correlations.
- Calculate key corporate risk metrics including margin distribution percentiles, probability of loss, Expected Shortfall (CVaR 95%), and the 0-100 Vulnerability Score.
- Implement CVaR-optimal hedging ratio optimization for forwards, options, and zero-cost collars using Garman-Kohlhagen and smile-consistent Monte Carlo simulations.
- Build risk governance framework with Kupiec POF VaR backtesting, historical stress scenarios (2008 crisis, COVID-19 shock), reverse stress testing, and Office des Changes regulatory rules.
- Deploy asynchronous FastAPI application server featuring API-key authentication, anti-SSRF protections, and multi-database persistence (PostgreSQL, MongoDB, Neo4j).
