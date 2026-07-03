<br>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/svg/logo_vl.svg">
    <img src="assets/svg/logo.svg" alt="Parity" width="350">
  </picture>
</p>

<br>

## Parity

Currency risk decision engine for importers and e-commerce merchants (codename `Xi`). It quantifies FX exposure by `Monte Carlo` simulation, produces a **Vulnerability Score** from 0 to 100, and recommends the optimal hedge such as a forward, an option, or a collar, with its cost and benefit fully quantified.

> **Private and proprietary.** Not licensed for redistribution. Internal use only.

## Table of Contents

| Section | Description |
|---|---|
| [Overview](#overview) | What Parity does and who it serves |
| [Capabilities](#capabilities) | Quantitative and platform features |
| [Requirements](#requirements) | Runtime and stack versions |
| [Quick Start](#quick-start) | Install, test, and run |
| [API](#api) | REST endpoints |
| [Model Options](#model-options) | Simulation and volatility parameters |
| [Configuration](#configuration) | Environment variables |
| [Architecture](#architecture) | Package layout and dependencies |
| [Testing](#testing) | Test suite and coverage |
| [License](#license) | Usage terms |

## Overview

An SME that buys in `USD` or `EUR` and resells 60 to 120 days later can watch its entire margin evaporate if the currency rises between order and delivery. Parity turns that uncertainty into a decision. It fetches historical exchange rates, estimates volatility, simulates the delivery-date rate over hundreds of thousands of scenarios, and translates the outcome into a margin distribution, a vulnerability score, and a concrete hedging recommendation with quantified cost and benefit.

The engine is built as a strict hexagonal architecture: a pure computation core with no knowledge of the network, databases, or transport, surrounded by adapters for data, persistence, and a REST API. Every external dependency is injected through a port, which keeps the core fully testable and lets a new data source, for example Bank Al-Maghrib for the `MAD`, plug in without touching the model.

## Capabilities

| Area | Techniques |
|---|---|
| Simulation | Risk-neutral `GBM` with covered interest rate parity drift, `Heston` stochastic volatility, `Student-t` fat tails, `Merton` jumps, `Sobol` sampling with antithetic variates |
| Volatility | `historical`, `EWMA` (RiskMetrics), `GARCH(1,1)` by maximum likelihood, with automatic fallback |
| Hedging | `CVaR` optimal hedge ratio, `Garman-Kohlhagen` and smile-consistent `Monte Carlo` pricing, comparison of unhedged, forward, option, and collar |
| Portfolio | Multi-currency netting, correlated simulation with `Cholesky`, portfolio `VaR` and `CVaR`, diversification benefit, dynamic `DCC-GARCH` correlations |
| Governance | `Kupiec` backtesting, deterministic stress tests, `2008` and `COVID-19` historical replay, reverse stress test, Office des Changes rules engine |
| Monitoring | Inter-run comparison (risk escalation, score jump, spot move) with console, webhook, and email alert sinks |
| Platform | Hardened `FastAPI` service, `PostgreSQL`, `MongoDB`, and `Neo4j` persistence, optional `Groq` AI narrative |

## Requirements

| Package | Version |
|---|---|
| Python | 3.11+ |
| NumPy | 1.26+ |
| SciPy | 1.13+ |
| pandas | 2.2+ |
| FastAPI | 0.115+ |
| Uvicorn | 0.34+ |
| pydantic | 2.10+ |

Optional integrations: `SQLAlchemy` with `psycopg2` for PostgreSQL, `pymongo` for MongoDB, `neo4j` for the exposure graph, `groq` for the AI narrative, and `python-dotenv` for `.env` loading.

## Quick Start

```bash
cp .env.example .env                                # all variables optional
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[api,db,ai,dotenv,dev]"
pytest -q                                           # 361 tests
uvicorn api.main:app --port 8000                    # docs at /docs
```

The engine runs with zero configuration, using free ECB rates and in-memory storage. Fill in `.env` to enable persistence, the AI narrative, or API authentication. A first request:

```bash
curl -X POST http://localhost:8000/api/v1/simulations \
  -H "Content-Type: application/json" \
  -d '{"order": {"amount_foreign": 200000, "foreign_currency": "USD",
       "domestic_currency": "EUR", "delivery_date": "2026-10-01",
       "target_margin_pct": 0.15, "domestic_rate": 0.021, "foreign_rate": 0.043}}'
```

## API

The REST root is `/api/v1` and interactive documentation is served at `/docs`. When `XI_API_KEY` is set, every route requires the `X-API-Key` header, except the public `/health` check.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Service status and version (public) |
| POST | `/api/v1/simulations` | Risk simulation, hedging decision, instrument comparison, alerts |
| GET | `/api/v1/simulations/history` | Persisted simulation history with currency filters |
| GET | `/api/v1/simulations/{id}` | Fetch a single persisted simulation |
| GET | `/api/v1/exposure` | Currency exposure graph |
| POST | `/api/v1/portfolio/simulations` | Multi-currency portfolio risk |
| POST | `/api/v1/stress-tests` | Deterministic and historical stress tests |
| POST | `/api/v1/compliance` | Office des Changes assessment (indicative) |
| POST | `/api/v1/backtests/var` | VaR model backtesting with the Kupiec test |

## Model Options

The `options` block of `POST /simulations` selects the modeling method. All fields are optional and default to the fastest baseline.

| Option | Values | Default |
|---|---|---|
| `market_model` | `gbm`, `heston` | `gbm` |
| `volatility_model` | `historical`, `ewma`, `garch` | `historical` |
| `return_distribution` | `normal`, `student_t` | `normal` |
| `sampling_method` | `pseudo_random`, `sobol` | `pseudo_random` |
| `jumps` | object with `intensity_annual`, `mean_log_jump`, `std_log_jump` | none |

## Configuration

All variables are optional and prefixed with `XI_`. The full list lives in [`.env.example`](.env.example).

**Application and security**

| Variable | Default | Description |
|---|---|---|
| `XI_API_KEY` | | When set, the `X-API-Key` header becomes mandatory |
| `XI_ALLOWED_FX_HOSTS` | `api.frankfurter.dev` | Data host allowlist (anti-SSRF) |
| `XI_HTTP_TIMEOUT_SECONDS` | `10.0` | Data call timeout |
| `XI_RATE_LIMIT_PER_SECOND` | `10.0` | Max request rate to the rate provider |
| `XI_CACHE_TTL_SECONDS` | `3600.0` | Exchange rate cache lifetime |

**Persistence (optional)**

| Variable | Default | Description |
|---|---|---|
| `XI_POSTGRES_DSN` | | PostgreSQL DSN for structured history |
| `XI_MONGODB_URI` | | MongoDB URI for result documents |
| `XI_MONGODB_DATABASE` | `xi` | Mongo database name |
| `XI_NEO4J_URI` | | Neo4j URI for the exposure graph |
| `XI_NEO4J_USERNAME`, `XI_NEO4J_PASSWORD` | | Neo4j credentials |
| `XI_NEO4J_DATABASE` | `neo4j` | Neo4j database (the instance ID on Aura) |

**AI (optional)**

| Variable | Default | Description |
|---|---|---|
| `XI_GROQ_API_KEY` | | Groq key for the AI narrative |
| `XI_GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model |

## Architecture

Strict hexagonal layering with no circular dependencies. The computation core is testable in isolation; every external dependency is injected through a port (Protocol).

| Package | Role | Depends on |
|---|---|---|
| `core/models` | Domain and pure computation (Monte Carlo, Heston, GARCH, DCC, hedging, stress, compliance) | none |
| `core/io` | FX data and network adapters (Frankfurter, secure session, cache, rate limiter) | `core/models` |
| `core/app` | Orchestration (`MarginRiskEngine`, `PortfolioRiskEngine`) | `core` |
| `db` | Persistence (in-memory, PostgreSQL, MongoDB, Neo4j, composite) | `core` |
| `ai` | AI narrative (Groq, import-guarded) | `core` |
| `api` | FastAPI service and `api/monitoring` (scheduler, alert sinks) | `core`, `db`, `ai` |

## Testing

| Metric | Value |
|---|---|
| Tests | 361 |
| Coverage | 98% |
| Runner | pytest |

Run the full suite with `pytest -q`. Tests use mocked providers and in-memory storage, so no network access or live database is required.

## License

Proprietary. All rights reserved. No use, copy, or distribution without written permission from the owner.
