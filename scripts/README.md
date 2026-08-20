# Parity Scripts & Tooling Directory

This directory contains standalone execution scripts, empirical backtesting pipelines, and DevOps provisioning tools for the **Parity** quantitative platform.

## Directory Structure

```
scripts/
├── benchmarks/
│   ├── verify_engine_benchmarks.py    # Direct Core Engine vs Secured REST API consistency checks
│   ├── benchmark_institutional_pnl.py # Non-overlapping multi-horizon PnL risk attribution
│   └── compute_audit_metrics.py       # Full calculations & metrics for LaTeX audit reports
├── backtesting/
│   └── run_empirical_backtest.py      # Basel III Kupiec POF & Expected Shortfall backtesting suite
└── ops/
    ├── deploy_vm.sh                   # Remote SSH VM provisioning with full Docker stack
    └── supabase_rls_fix.sql           # Row Level Security (RLS) policies for Supabase / PostgreSQL
```

## 1. Benchmarks (`scripts/benchmarks/`)

### Verify Engine Consistency (`verify_engine_benchmarks.py`)
Feeds standardized business cases into both the local Python core and the secured REST API, certifying that closed-form formulas and Monte Carlo outputs match with $0.000000$ deviation.
```bash
python scripts/benchmarks/verify_engine_benchmarks.py
```

### Institutional PnL Attribution (`benchmark_institutional_pnl.py`)
Computes unhedged vs forward-hedged margin percentiles and CVaR protection gains across independent (non-overlapping) delivery horizons.
```bash
python scripts/benchmarks/benchmark_institutional_pnl.py
```

### Compute Audit Metrics (`compute_audit_metrics.py`)
Calculates the exact multi-tranche aerospace portfolio figures, Garman-Kohlhagen Greeks matrix, and stress-test scenarios for institutional audit reporting.
```bash
python scripts/benchmarks/compute_audit_metrics.py
```

## 2. Regulatory Backtesting (`scripts/backtesting/`)

### Basel III Empirical Backtests (`run_empirical_backtest.py`)
Runs rolling window parametric VaR and Expected Shortfall backtests on European Central Bank (ECB) daily currency series under Gaussian and heavy-tailed Student-$t$ distributions.
```bash
python scripts/backtesting/run_empirical_backtest.py
```

## 3. DevOps & Database Operations (`scripts/ops/`)

### Remote VM Deployment (`deploy_vm.sh`)
Deploys the Parity stack (API, Redis, MLflow, Spark) over SSH to a remote server.
```bash
./scripts/ops/deploy_vm.sh <ssh-user> <host-ip>
```

### Supabase Row-Level Security (`supabase_rls_fix.sql`)
Enables strict PostgreSQL RLS policies across all public tables, securing direct PostgREST client exposure while allowing server-side owner bypass.
