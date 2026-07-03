<br>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/svg/logo_vl.svg">
    <img src="assets/svg/logo.svg" alt="Parity" width="280">
  </picture>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.6.0-4AAFFD.svg" alt="Version">
  <img src="https://img.shields.io/badge/python-3.11%2B-50B8FD.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/tests-361%20passing-53BCFD.svg" alt="Tests">
  <img src="https://img.shields.io/badge/coverage-98%25-56C0FD.svg" alt="Coverage">
  <img src="https://img.shields.io/badge/license-Proprietary-4DB3FD.svg" alt="License">
</p>

<br>

## Parity

Currency risk decision engine for importers and e-commerce merchants (codename `Xi`). It quantifies FX exposure by `Monte Carlo` simulation, produces a **Vulnerability Score** (0 to 100), and recommends the optimal hedge (forward, option, or collar) with its cost and benefit.

> **Private and proprietary.** Not licensed for redistribution. Internal use only.

## Highlights

- **Simulation**: `GBM` with covered interest rate parity drift, `Heston` stochastic volatility, `Student-t` tails, `Merton` jumps, `Sobol` sampling.
- **Volatility and correlation**: `historical`, `EWMA`, `GARCH(1,1)`; portfolio `DCC-GARCH`.
- **Hedging**: `CVaR`-optimal ratio, `Garman-Kohlhagen` and smile-consistent Monte Carlo pricing, forward / option / collar comparison.
- **Risk and governance**: portfolio `VaR` / `CVaR`, `Kupiec` backtesting, stress tests with 2008 and COVID replay, Office des Changes rules, inter-run monitoring with alerts.
- **Platform**: hardened `FastAPI` service, `PostgreSQL` / `MongoDB` / `Neo4j` persistence, optional `Groq` AI narrative.

## Quick Start

```bash
cp .env.example .env                                # all variables optional
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[api,db,ai,dotenv,dev]"
pytest -q                                           # 361 tests
uvicorn api.main:app --port 8000                    # docs at /docs
```

The engine runs with zero configuration (free ECB rates, in-memory storage). Fill in `.env` to enable persistence, the AI narrative, or API authentication.

## API

REST root `/api/v1`. When `XI_API_KEY` is set, all routes require the `X-API-Key` header (except `/health`).

| Method | Endpoint | Description |
|---|---|---|
| POST | `/simulations` | Risk simulation, hedging, instrument comparison, alerts |
| GET | `/simulations/history` | Persisted simulation history |
| GET | `/simulations/{id}` | Fetch a persisted simulation |
| GET | `/exposure` | Currency exposure graph |
| POST | `/portfolio/simulations` | Multi-currency portfolio risk |
| POST | `/stress-tests` | Deterministic and historical stress tests |
| POST | `/compliance` | Office des Changes assessment (indicative) |
| POST | `/backtests/var` | VaR backtesting (Kupiec) |

## Configuration

All variables are optional and prefixed `XI_`. Full list in [`.env.example`](.env.example).

| Group | Variables |
|---|---|
| Security | `XI_API_KEY`, `XI_ALLOWED_FX_HOSTS`, `XI_RATE_LIMIT_PER_SECOND` |
| Persistence | `XI_POSTGRES_DSN`, `XI_MONGODB_URI`, `XI_NEO4J_URI` (with user, password, database) |
| AI | `XI_GROQ_API_KEY`, `XI_GROQ_MODEL` |

## Architecture

Strict hexagonal layering, no circular dependencies. The computation core is testable in isolation; every external dependency is injected through a port (Protocol).

| Package | Role |
|---|---|
| `core/models` | Domain and pure computation (Monte Carlo, Heston, GARCH, DCC, hedging, stress, compliance) |
| `core/io` | FX data and network adapters (Frankfurter, secure session, cache, rate limiter) |
| `core/app` | Orchestration (`MarginRiskEngine`, `PortfolioRiskEngine`) |
| `db` | Persistence (in-memory, PostgreSQL, MongoDB, Neo4j) |
| `ai` | AI narrative (Groq) |
| `api` | FastAPI service and `api/monitoring` (scheduler, alert sinks) |

## License

Proprietary. All rights reserved. No use, copy, or distribution without written permission from the owner.
