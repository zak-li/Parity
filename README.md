<br>

<p align="center">
  <a>
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset=".github/assets/svg/parity_brand_banner_dark.svg">
      <img src=".github/assets/svg/parity_brand_banner_light.svg" alt="Parity" width="100%">
    </picture>
  </a>
</p>

<br>

## Parity

> `Parity` (codename `Xi`): a currency risk decision engine for importers and e-commerce merchants. It quantifies FX exposure, scores vulnerability, and recommends the optimal hedge directly from the numbers.

Parity quantifies FX exposure by [`Monte Carlo`](core/models/monte_carlo.py) simulation, produces a `Vulnerability Score` from `0` to `100`, and recommends the optimal hedge such as a `forward`, an `option`, or a `collar`, with its cost and benefit fully quantified.

<br>

<p align="center">
  <a>
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset=".github/assets/charts/parity_quadrant_dark.png?v=3">
      <img src=".github/assets/charts/parity_quadrant_light.png?v=3" alt="Parity Predictive Engine Accuracy" width="100%">
    </picture>
  </a>
</p>

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Docker](#docker)
- [Core API](#core-api)
- [Observability](#observability)
- [Settings](#settings)
- [License](#license)

## Features

Parity simulates currency market uncertainty across hundreds of thousands of stochastic market scenarios to quantify downside margin risk and automate hedging decisions before transactions settle.

To generate these forward paths, the engine pairs [Geometric Brownian Motion (GBM)](core/models/monte_carlo.py) with Covered Interest Parity (`CIP`) drift, [Heston stochastic volatility](core/models/heston.py), and [Merton jump-diffusion](core/models/monte_carlo.py) processes, while calibrating dynamic [GARCH(1,1)](core/models/volatility.py) volatility clustering, fat-tailed `Student-t` return distributions, and [Dynamic Conditional Correlation (DCC-GARCH)](core/models/dcc.py) for multi-currency portfolios.

The platform automates derivative valuation and trade-off analysis to determine optimal hedging structures for commercial transactions and corporate portfolios:
- Prices and ranks Forwards, European Vanilla Options, and Zero-Cost Collars with closed-form [Garman-Kohlhagen](core/models/instruments.py) models with exact numerical cap solving (`brentq`).
- Provides full analytical Greeks ($\Delta$, $\Gamma$, $\nu$, $\Theta$, $\rho_d$, $\rho_f$) for precise hedging desk risk management in [`core/models/instruments.py`](core/models/instruments.py).

For corporate treasuries managing multi-date currency commitments, Parity delivers layered [cashflow ladder hedging](core/models/ladder.py), deterministic macroeconomic [stress testing](core/models/stress.py), and [reverse stress testing](core/models/stress.py) to identify exact breakeven exchange rates ($S^*$). Model accuracy is formally certified under Basel III regulatory standards using the [Kupiec LR test](core/models/backtesting.py) on `VaR 95%` ($p\text{-value} = 0.8214$) and [Acerbi-Székely](core/models/backtesting.py) Expected Shortfall backtests.

The platform connects seamlessly to enterprise workflows by ingesting foreign sales and purchase orders through native ETL connectors ([`Shopify`](core/connectors/shopify.py), [`WooCommerce`](core/connectors/woocommerce.py), [`Stripe`](core/connectors/stripe.py), [`Odoo`](core/connectors/odoo.py)) while delivering real-time [drift alerts](core/models/monitoring.py), regulatory compliance checks ([`Office des Changes / IGOC`](core/models/compliance.py)), and executive AI risk commentary with [Groq / LLaMA 3.3](ai/groq_narrator.py).

## Quick Start

### 1. Installation

Install the package directly from source:

```bash
git clone https://github.com/zak-li/Parity.git
cd Parity
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[api,db,ai,dotenv,dev]"
```

### 2. Python SDK Usage (`import Parity`)

The engine can be embedded directly into quantitative pipelines and Python applications:

```python
import datetime as dt
import Parity

# 1. Initialize API License (see core/licensing.py)
Parity.init(api_key="your-api-key")

# 2. Instantiate the Risk Engine (see core/app/risk_engine.py)
engine = Parity.MarginRiskEngine()

# 3. Define an international commercial order
order = Parity.OrderInput(
    amount_foreign=250000.0,  # 250,000 USD
    foreign_currency="USD",
    domestic_currency="EUR",
    order_date=dt.date.today(),
    delivery_date=dt.date.today() + dt.timedelta(days=90),
    target_margin_pct=0.18,  # 18% target margin
    min_acceptable_margin_pct=0.05,  # 5% floor
    domestic_rate=0.021,  # 2.1% EUR rate
    foreign_rate=0.043,  # 4.3% USD rate
    n_simulations=10000,
    lookback_days=180,
    seed=42,
)

# 4. Run stochastic simulation
result = engine.run(order)

print(f"Spot Rate S0                 : {result.spot_rate_order_date:.4f}")
print(f"Theoretical Forward (CIP)    : {result.hedge.theoretical_forward_rate:.4f}")
print(f"Annualized Volatility        : {result.annualized_volatility * 100:.2f}%")
print(f"Expected Shortfall (CVaR 5%) : {result.expected_shortfall_margin_pct * 100:.2f}%")
print(f"Recommended Instrument       : {result.hedge.recommended_instrument.value}")
```

Price FX options and retrieve analytical Greek sensitivities instantly:

```python
from Parity.models.instruments import garman_kohlhagen_greeks

greeks = garman_kohlhagen_greeks(
    spot=0.8561, strike=0.8515, rd=0.021, rf=0.043, sigma=0.062, t=0.25, kind="call"
)
print(f"Delta: {greeks.delta:.4f} | Gamma: {greeks.gamma:.4f} | Vega: {greeks.vega:.4f}")
```

### 3. Hardened REST API Service

Launch the secured [`FastAPI`](api/main.py) service on localhost:

```bash
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Post an exposure order to evaluate hedging recommendations:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/simulations \
  -H "X-API-Key: saEE4TKha-i0RlfVlbRLUob2M8cYLds3v9-FeqkCn3g" \
  -H "Content-Type: application/json" \
  -d '{
    "order": {
      "amount_foreign": 200000,
      "foreign_currency": "USD",
      "domestic_currency": "EUR",
      "delivery_date": "2026-10-01",
      "target_margin_pct": 0.15,
      "domestic_rate": 0.021,
      "foreign_rate": 0.043
    }
  }'
```

The modeling assumptions, limits, and validation are covered in [`docs/MODELS.md`](docs/MODELS.md).

### 4. Command Line Interface (CLI)

Perform risk assessments and compare hedges without starting an API service using [`core/cli.py`](core/cli.py):

```bash
# Print general usage
parity --help

# Run order simulation (compact syntax)
parity sim -a 200000 -f USD -d EUR -t 2026-10-01 -m 0.15

# Export structured JSON
parity sim -a 200000 -f USD -t 2026-10-01 --json

# Run connectivity diagnostics
parity health
```

### Docker

[`docker-compose.yml`](docker-compose.yml) brings up the backend platform. It runs the API and the engines' three scale services: a `Redis` FX-rate cache and rate limiter ([`core/io/fx/frankfurter.py`](core/io/fx/frankfurter.py)), an `MLflow` tracking server that records every simulation as a run with its parameters and risk metrics ([`core/app/tracking.py`](core/app/tracking.py)), and an `Apache Spark` cluster that scores a book of orders in parallel ([`core/app/distributed.py`](core/app/distributed.py)):

```bash
docker compose up --build
```

The API listens on `http://localhost:8000` (health check at [`/health`](api/routes.py)) and runs as a non-root user. The stack uses host networking, so each service is reachable at `127.0.0.1:<port>` on the host and at `<host-ip>:<port>` from other machines (API `8000`, Redis `6379`, MLflow `5000`, Spark `7077`/`8080`). Databases stay in the cloud (configured in [`.env`](.env.example)); the API reaches the co-located services over loopback, and the same `XI_REDIS_URL` / `XI_MLFLOW_TRACKING_URI` / `XI_SPARK_MASTER` variables point a local machine at a remote host. Provision a remote host over SSH with [`scripts/ops/deploy_vm.sh`](scripts/ops/deploy_vm.sh):

```bash
./scripts/ops/deploy_vm.sh <ssh-user> <host-ip>
```

Process high-volume order batches on the distributed Spark cluster:

```bash
python -m core.app.distributed --input core/app/samples/example_orders.json
```

PostgreSQL schema lifecycle and versioning are managed with Alembic:

```bash
alembic upgrade head
```

## Core API

The API is rooted at `/api/v1` and protected by mandatory authentication (`X-API-Key` or `Auth0` Bearer token). Routes are defined in [`api/routes.py`](api/routes.py) and [`api/routers/connectors.py`](api/routers/connectors.py).

These endpoints run simulations and expose their results:

| Method | Endpoint | Description |
|---|---|---|
| GET | [`/health`](api/routes.py) | Liveness check. *public* |
| POST | [`/api/v1/simulations`](api/routes.py) | Risk simulation, hedging decision, instrument comparison, alerts |
| GET | [`/api/v1/simulations/history`](api/routes.py) | Persisted simulation history with currency filters |
| GET | [`/api/v1/simulations/{id}`](api/routes.py) | Fetch a single persisted simulation |
| GET | [`/api/v1/exposure`](api/routes.py) | Currency exposure graph |
| GET | [`/api/v1/me`](api/routes.py) | Identity of the authenticated client |

These admin endpoints manage per-client API keys (master key or open dev mode only) through [`api/keys.py`](api/keys.py):

| Method | Endpoint | Description |
|---|---|---|
| POST | [`/api/v1/keys`](api/keys.py) | Mint a key for a client; returns the plaintext once |
| GET | [`/api/v1/keys`](api/keys.py) | List keys (metadata only, never the secret) |
| DELETE | [`/api/v1/keys/{id}`](api/keys.py) | Revoke a key |

These endpoints ingest exposure automatically (ETL) from e-commerce and ERP platforms through [`api/routers/connectors.py`](api/routers/connectors.py):

| Method | Endpoint | Description |
|---|---|---|
| POST | [`/api/v1/connectors/shopify/import`](api/routers/connectors.py) | Fetch sales/revenue from [`Shopify`](core/connectors/shopify.py) |
| POST | [`/api/v1/connectors/woocommerce/import`](api/routers/connectors.py) | Fetch orders from [`WooCommerce`](core/connectors/woocommerce.py) |
| POST | [`/api/v1/connectors/stripe/import`](api/routers/connectors.py) | Fetch successful charges from [`Stripe`](core/connectors/stripe.py) |
| POST | [`/api/v1/connectors/odoo/import`](api/routers/connectors.py) | Fetch purchase orders (costs) from [`Odoo`](core/connectors/odoo.py) ERP |

These endpoints cover portfolio risk, hedging tools, stress testing, compliance, and backtesting:

| Method | Endpoint | Description |
|---|---|---|
| POST | [`/api/v1/portfolio/simulations`](api/routes.py) | Multi-currency portfolio risk with per-currency `CVaR` attribution in [`core/models/portfolio.py`](core/models/portfolio.py) |
| POST | [`/api/v1/ladder/simulations`](api/routes.py) | Cashflow ladder: multi-date exposure and layered hedging in [`core/models/ladder.py`](core/models/ladder.py) |
| POST | [`/api/v1/hedge/greeks`](api/routes.py) | Closed-form FX option Greeks ([`Garman-Kohlhagen`](core/models/instruments.py)) |
| POST | [`/api/v1/stress-tests`](api/routes.py) | Deterministic and historical stress tests with [`core/models/stress.py`](core/models/stress.py) |
| POST | [`/api/v1/compliance`](api/routes.py) | Office des Changes assessment ([`core/models/compliance.py`](core/models/compliance.py)) |
| POST | [`/api/v1/backtests/var`](api/routes.py) | `VaR` model backtesting with the `Kupiec` test in [`core/models/backtesting.py`](core/models/backtesting.py) |
| POST | [`/api/v1/backtests/es`](api/routes.py) | Expected Shortfall backtest ([`Acerbi-Székely`](core/models/backtesting.py)) |

### Options

The `options` block of `POST /api/v1/simulations` selects the modeling method. All fields are optional and default to the fastest baseline.

| Option | Values | Default |
|---|---|---|
| `market_model` | `gbm`, `heston` | `gbm` |
| `volatility_model` | `historical`, `ewma`, `garch` | `historical` |
| `return_distribution` | `normal`, `student_t` | `normal` |
| `sampling_method` | `pseudo_random`, `sobol` | `pseudo_random` |
| `jumps` | object with `intensity_annual`, `mean_log_jump`, `std_log_jump` | none |

## Observability

Production monitoring is enabled out of the box: inbound requests carry an `X-Request-ID` (echoed from the caller or generated) bound to structured `JSON` logs, so a single request can be traced end to end. `Prometheus` metrics such as request counts and latency histograms, labelled by method, route template, and status, are served at [`GET /metrics`](api/observability.py), which should be restricted to an internal network in production.

## Settings

These variables are all optional and share the `XI_` prefix. The complete reference is in [`.env.example`](.env.example).

| Variable | Default | Description |
|---|---|---|
| `XI_API_KEY` | | Master key; when set, the `X-API-Key` header becomes mandatory ([`core/licensing.py`](core/licensing.py)) |
| `XI_API_KEY_PEPPER` | | Secret pepper for per-client API-key hashing (set in production) |
| `XI_ENV` | `development` | Environment mode (`development`, `production`) |
| `XI_API_RATE_LIMIT_PER_SECOND` | `25` | Inbound per-client rate limit |
| `XI_API_RATE_LIMIT_BURST` | `50` | Inbound per-client burst size |
| `XI_API_MAX_CONCURRENCY` | `8` | Max simultaneous requests before `503` |
| `XI_API_REQUEST_TIMEOUT_SECONDS` | `30` | Request timeout before `504` |
| `XI_LOG_LEVEL` | `INFO` | JSON log level |
| `XI_DB_AUTO_CREATE` | `1` | Set `0` in production; manage the schema with Alembic |
| `XI_DB_STRICT` | `0` | When set to `1`, unreachable database fails closed instead of falling back to memory |
| `XI_ALLOWED_FX_HOSTS` | `api.frankfurter.dev` | Data host allowlist (anti-SSRF) |
| `XI_FX_PROVIDERS` | `frankfurter,exchangerate_api` | Prioritized FX provider chain |
| `XI_EXCHANGERATE_API_KEY` | | API key for ExchangeRate-API |
| `XI_FIXER_API_KEY` | | API key for Fixer.io |
| `XI_HTTP_TIMEOUT_SECONDS` | `10.0` | Data call timeout |
| `XI_RATE_LIMIT_PER_SECOND` | `10.0` | Max request rate to the rate provider |
| `XI_CACHE_TTL_SECONDS` | `3600.0` | Exchange rate cache lifetime |
| `XI_POSTGRES_DSN` | | PostgreSQL DSN for structured history |
| `XI_MONGODB_URI` | | MongoDB URI for result documents |
| `XI_MONGODB_DATABASE` | `xi` | Mongo database name |
| `XI_NEO4J_URI` | | Neo4j URI for the exposure graph |
| `XI_NEO4J_USERNAME`, `XI_NEO4J_PASSWORD` | | Neo4j credentials |
| `XI_NEO4J_DATABASE` | `neo4j` | Neo4j database (the instance ID on Aura) |
| `XI_GROQ_API_KEY` | | Groq key for the AI narrative ([`ai/groq_narrator.py`](ai/groq_narrator.py)) |
| `XI_GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model |
| `XI_REDIS_URL` | | Shared FX cache + rate limiter (also used by the full-stack deployment) |
| `XI_AUTH0_DOMAIN` | | Auth0 tenant domain (e.g. `dev-xxx.eu.auth0.com`) |
| `XI_AUTH0_CLIENT_ID` | | Auth0 application client ID |
| `XI_AUTH0_AUDIENCE` | `api://default` | Auth0 API audience |
| `XI_CORS_ALLOW_ORIGINS` | | Comma-separated browser origins allowed to call the API |
| `XI_MLFLOW_TRACKING_URI` | | MLflow server; logs each run when set (`[mlflow]` extra) |
| `XI_MLFLOW_EXPERIMENT` | `parity-simulations` | MLflow experiment name |
| `XI_SPARK_MASTER` | `local[*]` | Spark master for batch simulations (`[spark]` extra) |

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).
