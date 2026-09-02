# Models: assumptions, limits, and validation

This document describes what the Parity engine computes, the assumptions behind
each model, its `known limitations`, and the numerical checks that back it.
Figures are `indicative` and do not constitute investment advice.

## 1. Delivery-date rate simulation

The delivery-date exchange rate is simulated under the domestic risk-neutral
measure.

- `GBM (default).` `S_T = S_0 · exp((μ − ½σ²)·T + σ·√T·Z)`, with drift
  `μ = r_d − r_f` (covered interest rate parity), so `E[S_T] = S_0·e^{(r_d−r_f)T}`
  equals the theoretical forward.
- `Optional extensions.` Heston stochastic volatility, Student-t fat tails,
  and Merton log-normal jumps (with drift compensator so the mean is preserved).
- `Sampling.` Pseudo-random with antithetic variates, or scrambled `Sobol`
  quasi-random sequences for faster convergence, inverted using high-performance
  C kernels (`scipy.special.ndtri`).

`Limits.` Volatility is constant per order (no term structure); jumps and
Heston parameters are user-supplied, not calibrated to a live option surface.

`Validation` (see `core/tests`): `E[S_T]` matches the CIP forward to ~0.01%;
standard error decreases as `1/√N`; Sobol reduces the forward error by ~100×
versus pseudo-random at the same sample count.

## 2. Volatility and correlation

- `Estimators.` `historical`, `EWMA` (RiskMetrics λ = 0.94), and `GARCH(1,1)`
  with automatic fallback to EWMA when the fit does not converge.
- `GARCH uses variance targeting`: `ω` is constrained so the long-run variance
  equals the sample variance and only `(α, β)` are optimized, a much
  better-conditioned problem than the joint `(ω, α, β)` search.
- `Portfolio correlations` with dynamic `DCC-GARCH`.
- `Tail-dependence copulas`: Gaussian copula and multivariate `Student-t Copula`
  (`CopulaType.STUDENT_T`), scaling correlated Gaussian vectors by $\sqrt{\nu / \chi^2(\nu)}$
  to capture systemic currency market crises and simultaneous devaluations.

`Limits.` Single-regime; no jumps in the volatility estimate itself.

`Validation.` On a constant-volatility series all estimators recover the true
σ within a few percent (regression test guards the GARCH variance-targeting fix,
which previously overstated volatility 2x to 5x). Multi-currency stress tests
certify higher Expected Shortfall under Student-t copulas than under Gaussian copulas.

## 3. Risk metrics

From the simulated margin distribution: percentiles, loss probability,
`Expected Shortfall (CVaR)` at α = 5% (mean of the worst-α tail, always ≤ the
expected margin), and a 0-100 `Vulnerability Score` combining loss probability
and tail severity.

## 4. Hedging instruments

- `Forward` priced at the CIP forward rate.
- `Vanilla Options` and `Zero-Cost Collars` priced with `Garman-Kohlhagen` (1983)
  or smile-consistent Monte Carlo.
- `Participating Forward (Par-Forward)`: A zero-cost structured derivative guaranteeing
  a maximum ceiling rate $K^*$ while preserving participation $\alpha \in (0, 1)$ in
  favorable exchange rate declines. The zero-cost strike is solved using Brent's method
  (`brentq`) enforcing $\text{Call}(K^*) = (1 - \alpha) \cdot \text{Put}(K^*)$.
- `Malz (1997) FX Volatility Smile`: Quadratic delta-based OTC smile parametrization
  calibrated on $\sigma_{\text{ATM}}$, 25-Delta Risk Reversal ($RR_{25}$), and
  25-Delta Butterfly ($BF_{25}$):
  $$\sigma(\Delta) = \sigma_{\text{ATM}} - 2 \cdot RR_{25} \cdot (\Delta - 0.5) + 16 \cdot BF_{25} \cdot (\Delta - 0.5)^2$$
  Yields strike-dependent implied volatilities injected directly into Garman-Kohlhagen.
- `Greeks` (delta, gamma, vega, theta, ρ_domestic, ρ_foreign) in closed form.
- `CVaR-optimal hedge ratio` by grid search plus local refinement across all 5 strategies.

`Limits.` Collars and participating forwards assume frictionless, mid-market
execution (no bid-ask spread).

`Validation.` Garman-Kohlhagen matches the Black-Scholes reference values and
put-call parity to 1e-9; every Greek matches a finite-difference check; the
Monte-Carlo option price matches the closed form within ~0.04%; participating
forward strikes satisfy the zero-premium condition to $|C - (1-\alpha)P| < 10^{-6}$.

## 5. Multi-date exposure (cashflow ladder)

Same-currency tranches at different horizons are simulated from `one shared
Brownian path` (longer horizons carry the shorter ones' moves), and compared
against a layered hedge that locks each tranche at its own forward.

## 6. Governance

- `VaR backtesting`: Kupiec proportion-of-failures test.
- `Expected Shortfall backtesting`: Acerbi-Székely (2014) `Test 2`, with a
  Monte-Carlo null distribution (a small p-value flags an ES that understates
  realized tail losses).
- `Stress tests`: deterministic shocks plus historical replay (2008, COVID-19)
  and a reverse stress test.
- `Compliance`: a versioned Office des Changes eligibility engine. `Indicative
  only`, not a regulatory opinion; confirm eligibility with your bank and the
  Office des Changes.

## Reproducing the figures

Numerical claims above are exercised by the test suite:

```bash
pip install -e ".[dev]"
pytest -q
```
