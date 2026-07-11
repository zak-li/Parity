<br>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset=".github/assets/svg/logo_2.svg">
    <img src=".github/assets/svg/logo.svg" alt="Parity" width="340">
  </picture>
</p>

<br>

<p align="center">
  <a href="https://github.com/zak-li/Parity/releases"><img src="https://img.shields.io/github/v/tag/zak-li/Parity?label=version&color=3A60F0" alt="Version"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL_3.0-2E77F3.svg" alt="License: AGPL 3.0"></a>
  <a href="https://github.com/zak-li/Parity/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/zak-li/Parity/ci.yml?label=CI&color=238EF6" alt="CI"></a>
  <a href="https://github.com/zak-li/Parity/issues"><img src="https://img.shields.io/github/issues/zak-li/Parity?color=17A6F9" alt="Issues"></a><br>
  <a href="https://github.com/zak-li/Parity/commits/main"><img src="https://img.shields.io/github/last-commit/zak-li/Parity?color=0CBDFC" alt="Last Commit"></a>
  <a href="https://docs.pytest.org/"><img src="https://img.shields.io/badge/tested_with-pytest-00D4FF.svg" alt="Tested with pytest"></a>
</p>

<br>

## Parity

> **Parity** (codename `Xi`): a currency risk decision engine for importers and e-commerce merchants. It quantifies FX exposure, scores vulnerability, and recommends the optimal hedge directly from the numbers.

Parity quantifies FX exposure by `Monte Carlo` simulation, produces a **Vulnerability Score** from 0 to 100, and recommends the optimal hedge such as a `forward`, an `option`, or a `collar`, with its cost and benefit fully quantified.

<br>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset=".github/assets/charts/parity_before_after_dark.png">
    <img src=".github/assets/charts/parity_before_after_light.png" alt="Parity Predictable Margins Chart" width="100%">
  </picture>
</p>

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [API](#api)
- [Observability](#observability)
- [Settings](#settings)
- [License](#license)

## Features

Parity turns raw currency exposure into a decision. It simulates the delivery-date exchange rate across hundreds of thousands of scenarios, captures volatility clustering and fat-tailed, jump-prone markets, and distils the outcome into margin percentiles, loss probability, tail risk (`Expected Shortfall`), and a 0 to 100 `Vulnerability Score`.

It then prices and compares hedging instruments, a `forward`, an `option`, and a `zero-cost collar`, to recommend the optimal hedge with its cost and benefit quantified. The same engine aggregates multi-currency portfolios with per-currency risk attribution, builds `layered hedges` across payment schedules, runs historical and hypothetical `stress tests`, backtests its own risk models, and checks regulatory hedging eligibility.

Operationally, it ingests exposure automatically from `e-commerce` and `ERP` platforms, secures access with `single sign-on` or `per-client keys`, and ships production-ready with `rate limiting`, `structured logging`, `metrics`, and an optional `AI narrative` that explains each result in plain language.

## Quick Start

The engine core requires the following packages:

| Package | Version |
|---|---|
| `Python` | 3.11+ |
| `NumPy` | 2.4+ |
| `SciPy` | 1.17+ |
| `pandas` | 3.0+ |
| `requests` | 2.34+ |

The following are optional and enable extra capabilities:

| Component | Role |
|---|---|
| `FastAPI` + `Uvicorn` | Hardened REST API service |
| `SQLAlchemy` + `psycopg2` | `PostgreSQL` structured history |
| `pymongo` | `MongoDB` result documents |
| `neo4j` | Currency exposure graph |
| `groq` | `AI` narrative generation |
| `python-dotenv` | `.env` file loading |
| `PyJWT` + `cryptography` | `Auth0` Single Sign-On (SSO) |
| `prometheus-client` | Prometheus `/metrics` endpoint |
| `redis` | Shared cache + rate limiter (multi-worker) |

### Setup

Install from source:

```bash
git clone https://github.com/zak-li/Parity.git
cd Parity
cp .env.example .env                # all variables are optional
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -e ".[api,db,ai,dotenv,dev]"
pytest -q                           # verify the install
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

The engine runs with zero configuration using free `ECB` rates and in-memory storage. The API is then live at `http://localhost:8000`, with interactive documentation at `/docs`.

Try it with a request:

```bash
curl -X POST http://localhost:8000/api/v1/simulations \
  -H "Content-Type: application/json" \
  -d '{"order": {"amount_foreign": 200000, "foreign_currency": "USD",
       "domestic_currency": "EUR", "delivery_date": "2026-10-01",
       "target_margin_pct": 0.15, "domestic_rate": 0.021, "foreign_rate": 0.043}}'
```

The response scores the exposure and ranks the hedges (trimmed):

```json
{
  "vulnerability_score": 32,
  "risk_level": "Moderate",
  "expected_terminal_rate": 1.0740,
  "margin_pct_percentiles": { "P5": 0.079, "P50": 0.135, "P95": 0.188 },
  "expected_shortfall_margin_pct": 0.079,
  "hedge": { "optimal_hedge_ratio": 1.0, "hedged_margin_pct": 0.135 },
  "instruments": [
    { "instrument": "none", "expected_margin_pct": 0.135, "cvar_margin_pct": 0.079 },
    { "instrument": "forward", "expected_margin_pct": 0.135, "cvar_margin_pct": 0.135 }
  ],
  "recommendation": "..."
}
```

The modeling assumptions, limits, and validation are covered in [`docs/MODELS.md`](docs/MODELS.md).

### Docker

Launch everything with Docker Compose:

```bash
docker compose up --build
```

The service listens on `http://localhost:8000` (health check at `/health`) and runs as a non-root user; published images are available on `ghcr.io/zak-li/parity`. With `PostgreSQL` the schema is managed by `Alembic`, so set `XI_DB_AUTO_CREATE=0` and apply migrations before starting:

```bash
alembic upgrade head
```

## API

The API is rooted at `/api/v1`, with Swagger docs at `/docs` and Prometheus metrics at `/metrics`. Once a credential is configured (`XI_API_KEY`, a per-client key, or `Auth0`), every `/api/v1` route requires it, while `/health` and `/metrics` stay public.

These endpoints run simulations and expose their results:

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Liveness check. *public* |
| POST | `/api/v1/simulations` | Risk simulation, hedging decision, instrument comparison, alerts |
| GET | `/api/v1/simulations/history` | Persisted simulation history with currency filters |
| GET | `/api/v1/simulations/{id}` | Fetch a single persisted simulation |
| GET | `/api/v1/exposure` | Currency exposure graph |

These endpoints ingest exposure automatically (ETL) from e-commerce and ERP platforms:

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/connectors/shopify/import` | Fetch sales/revenue from `Shopify` |
| POST | `/api/v1/connectors/woocommerce/import` | Fetch orders from `WooCommerce` |
| POST | `/api/v1/connectors/stripe/import` | Fetch successful charges from `Stripe` |
| POST | `/api/v1/connectors/odoo/import` | Fetch purchase orders (costs) from `Odoo` ERP |

These endpoints cover portfolio risk, hedging tools, stress testing, compliance, and backtesting:

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/portfolio/simulations` | Multi-currency portfolio risk with per-currency `CVaR` attribution |
| POST | `/api/v1/ladder/simulations` | Cashflow ladder: multi-date exposure and layered hedging |
| POST | `/api/v1/hedge/greeks` | Closed-form FX option Greeks (`Garman-Kohlhagen`) |
| POST | `/api/v1/stress-tests` | Deterministic and historical stress tests |
| POST | `/api/v1/compliance` | Office des Changes assessment (indicative) |
| POST | `/api/v1/backtests/var` | `VaR` model backtesting with the `Kupiec` test |
| POST | `/api/v1/backtests/es` | Expected Shortfall backtest (`Acerbi-Szekely`) |

### Options

The `options` block of `POST /simulations` selects the modeling method. All fields are optional and default to the fastest baseline.

| Option | Values | Default |
|---|---|---|
| `market_model` | `gbm`, `heston` | `gbm` |
| `volatility_model` | `historical`, `ewma`, `garch` | `historical` |
| `return_distribution` | `normal`, `student_t` | `normal` |
| `sampling_method` | `pseudo_random`, `sobol` | `pseudo_random` |
| `jumps` | object with `intensity_annual`, `mean_log_jump`, `std_log_jump` | none |

## Observability

Every request carries an `X-Request-ID` (echoed from the caller or generated) bound to structured `JSON` logs, so a single request can be traced end to end. `Prometheus` metrics such as request counts and latency histograms, labelled by method, route template, and status, are served at `GET /metrics`, which should be restricted to an internal network in production.

## Settings

These variables are all optional and share the `XI_` prefix. The complete reference is in [`.env.example`](.env.example).

| Variable | Default | Description |
|---|---|---|
| `XI_API_KEY` | | Master key; when set, the `X-API-Key` header becomes mandatory |
| `XI_API_KEY_PEPPER` | | Secret pepper for per-client API-key hashing (set in production) |
| `XI_API_RATE_LIMIT_PER_SECOND` | `25` | Inbound per-client rate limit |
| `XI_API_RATE_LIMIT_BURST` | `50` | Inbound per-client burst size |
| `XI_API_MAX_CONCURRENCY` | `8` | Max simultaneous requests before `503` |
| `XI_API_REQUEST_TIMEOUT_SECONDS` | `30` | Request timeout before `504` |
| `XI_LOG_LEVEL` | `INFO` | JSON log level |
| `XI_DB_AUTO_CREATE` | `1` | Set `0` in production; manage the schema with Alembic |
| `XI_ALLOWED_FX_HOSTS` | `api.frankfurter.dev` | Data host allowlist (anti-SSRF) |
| `XI_HTTP_TIMEOUT_SECONDS` | `10.0` | Data call timeout |
| `XI_RATE_LIMIT_PER_SECOND` | `10.0` | Max request rate to the rate provider |
| `XI_CACHE_TTL_SECONDS` | `3600.0` | Exchange rate cache lifetime |
| `XI_POSTGRES_DSN` | | PostgreSQL DSN for structured history |
| `XI_MONGODB_URI` | | MongoDB URI for result documents |
| `XI_MONGODB_DATABASE` | `xi` | Mongo database name |
| `XI_NEO4J_URI` | | Neo4j URI for the exposure graph |
| `XI_NEO4J_USERNAME`, `XI_NEO4J_PASSWORD` | | Neo4j credentials |
| `XI_NEO4J_DATABASE` | `neo4j` | Neo4j database (the instance ID on Aura) |
| `XI_GROQ_API_KEY` | | Groq key for the AI narrative |
| `XI_GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model |
| `XI_REDIS_URL` | | Shared cache + rate limiter for multi-worker deployments |
| `XI_AUTH0_DOMAIN` | | Auth0 tenant domain (e.g. `dev-xxx.eu.auth0.com`) |
| `XI_AUTH0_CLIENT_ID` | | Auth0 application client ID |
| `XI_AUTH0_AUDIENCE` | `api://default` | Auth0 API audience |

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).
