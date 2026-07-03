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

| Section |
|---|
| [Overview](#overview) |
| [Capabilities](#capabilities) |
| [Requirements](#requirements) |
| [Quick Start](#quick-start) |
| [API](#api) |
| [Model Options](#model-options) |
| [Configuration](#configuration) |
| [Architecture](#architecture) |
| [License](#license) |

## Overview

An SME that buys in `USD` or `EUR` and resells 60 to 120 days later can watch its entire margin evaporate if the currency rises between order and delivery. Parity turns that uncertainty into a decision. It fetches historical exchange rates, estimates volatility, simulates the delivery-date rate over hundreds of thousands of scenarios, and translates the outcome into a margin distribution, a vulnerability score, and a concrete hedging recommendation with quantified cost and benefit.

The engine is built as a strict hexagonal architecture: a pure computation core with no knowledge of the network, databases, or transport, surrounded by adapters for data, persistence, and a REST API. Every external dependency is injected through a port, which keeps the core fully testable and lets a new data source, for example Bank Al-Maghrib for the `MAD`, plug in without touching the model.

## Capabilities

The simulation core prices the delivery-date exchange rate under a risk-neutral `GBM` whose drift respects covered interest rate parity, with optional `Heston` stochastic volatility, `Student-t` fat tails, and `Merton` jumps, sampled with `Sobol` sequences and antithetic variates. Volatility is estimated by `historical`, `EWMA`, or `GARCH(1,1)` with automatic fallback, and portfolio correlations by dynamic `DCC-GARCH`. The resulting margin distribution yields percentiles, loss probability, Expected Shortfall (`CVaR`), and the Vulnerability Score.

On top of that distribution, the hedging engine computes the `CVaR` optimal hedge ratio and compares the unhedged position against a forward, an option, and a collar, priced with `Garman-Kohlhagen` or with smile-consistent `Monte Carlo` under Heston. Portfolios of several multi-currency orders are aggregated with per-currency netting, correlated simulation, portfolio `VaR` and `CVaR`, and a diversification benefit.

Governance and monitoring are built in. The engine backtests its `VaR` model with the `Kupiec` test, runs deterministic stress tests with `2008` and `COVID-19` historical replay and a reverse stress test, and evaluates hedging eligibility through a versioned Office des Changes rules engine. An inter-run monitor compares each new result against the previous one and dispatches typed alerts to console, webhook, or email sinks.

Everything is exposed through a hardened `FastAPI` service with API key authentication, an anti-`SSRF` host allowlist, token-bucket rate limiting, and security headers. Results persist on `PostgreSQL` for structured history, `MongoDB` for full documents, and `Neo4j` for the currency exposure graph, with an optional `Groq` AI narrative.

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

**1. Clone the repository**

```bash
git clone https://github.com/zak-li/Parity.git
cd Parity
```

**2. Create the environment file**

```bash
cp .env.example .env
```

All variables are optional. The engine runs with zero configuration using free ECB rates and in-memory storage. Fill in `.env` to enable persistence, the AI narrative, or API authentication.

**3. Create a virtual environment and install**

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[api,db,ai,dotenv,dev]"
```

**4. Run the test suite**

```bash
pytest -q
```

**5. Start the API**

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

The API is live at `http://localhost:8000` and the interactive documentation at `/docs`.

**6. Send a first request**

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

## License

Proprietary. All rights reserved. No use, copy, or distribution without written permission from the owner.
