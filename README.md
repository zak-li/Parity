<br>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/svg/logo_vl.svg">
    <img src="assets/svg/logo.svg" alt="Parity" width="280">
  </picture>
</p>

<br>

## Parity

Currency risk decision engine for importers and e-commerce merchants (codename `Xi`). It quantifies FX exposure by `Monte Carlo` simulation, produces a **Vulnerability Score** (0 to 100), and recommends the optimal hedge such as a forward, an option, or a collar, with its cost and benefit.

> **Private and proprietary.** Not licensed for redistribution. Internal use only.

## Capabilities

The simulation core prices the delivery-date exchange rate under a risk-neutral `GBM` with a covered interest rate parity drift, with optional `Heston` stochastic volatility, `Student-t` fat tails, and `Merton` jumps, sampled with `Sobol` sequences and antithetic variates. Volatility is estimated by `historical`, `EWMA`, or `GARCH(1,1)`, and portfolio correlations by `DCC-GARCH`. The resulting margin distribution yields percentiles, loss probability, Expected Shortfall (`CVaR`), and the Vulnerability Score.

On top of that distribution, the hedging engine computes the `CVaR` optimal hedge ratio and compares the unhedged position against a forward, an option, and a collar, priced with `Garman-Kohlhagen` or smile consistent `Monte Carlo` under Heston. It aggregates multi-currency portfolios with per-currency netting, portfolio `VaR` and `CVaR`, and a diversification benefit. Governance is built in through `Kupiec` backtesting, deterministic stress tests with `2008` and `COVID-19` historical replay, a versioned Office des Changes rules engine, and inter-run monitoring that dispatches typed alerts to console, webhook, or email sinks.

Everything is exposed through a hardened `FastAPI` service with API key authentication, an anti `SSRF` host allowlist, token-bucket rate limiting, and security headers. Results persist on `PostgreSQL` for structured history, `MongoDB` for full documents, and `Neo4j` for the currency exposure graph, with an optional `Groq` AI narrative. The suite ships with `361` tests at `98%` coverage.

## Quick Start

```bash
cp .env.example .env                                # all variables optional
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[api,db,ai,dotenv,dev]"
pytest -q                                           # 361 tests
uvicorn api.main:app --port 8000                    # docs at /docs
```

The engine runs with zero configuration, using free ECB rates and in-memory storage. Fill in `.env` to enable persistence, the AI narrative, or API authentication.

## API

The REST root is `/api/v1` and the interactive documentation is served at `/docs`. When `XI_API_KEY` is set, every route requires the `X-API-Key` header except the public `/health` check. The main entry point is `POST /simulations`, which returns the full risk analysis, hedging decision, instrument comparison, and inter-run alerts; persisted runs are retrieved through `GET /simulations/history` and `GET /simulations/{id}`, and the currency exposure graph through `GET /exposure`. Portfolio risk is computed by `POST /portfolio/simulations`, stress testing by `POST /stress-tests`, the Office des Changes assessment by `POST /compliance`, and VaR backtesting by `POST /backtests/var`.

## Configuration

All variables are optional and prefixed with `XI_`; the full list lives in [`.env.example`](.env.example). Security is configured through `XI_API_KEY`, `XI_ALLOWED_FX_HOSTS`, and `XI_RATE_LIMIT_PER_SECOND`. Persistence activates when `XI_POSTGRES_DSN`, `XI_MONGODB_URI`, or `XI_NEO4J_URI` (with their user, password, and database) are provided. The AI narrative is enabled by `XI_GROQ_API_KEY` and tuned with `XI_GROQ_MODEL`.

## License

Proprietary. All rights reserved. No use, copy, or distribution without written permission from the owner.
