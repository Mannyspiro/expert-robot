# Merlin Finance Mathematics Primitives v0.1

Status: deterministic research utility; not an investment recommendation or transaction system.

## Purpose

Provide small, dependency-free, unit-tested financial mathematics functions that can be reused by the Finance research adapter, business modelling, quantitative economics, and mathematical transfer engine.

## Initial functions

- `cagr(beginning_value, ending_value, years)`: endpoint compound annual growth rate, returned as a decimal fraction.
- `total_return(beginning_value, ending_value)`: simple endpoint return.
- `npv(rate, cash_flows)`: periodic net present value, with period-zero cash flow first.
- `irr(cash_flows)`: periodic internal rate of return using bracketed bisection. It rejects non-conventional cash flows with multiple sign changes rather than silently selecting a root.
- `discounted_cash_flow(cash_flows, discount_rate, terminal_value)`: discounted forecast cash flows and terminal value, with forecast periods numbered 1..N.

## Conventions and limitations

- Rates and returns are decimal fractions: 0.10 means 10%.
- Inputs must be finite numeric values; booleans, NaN and infinity are rejected.
- CAGR requires positive beginning and ending values and a positive duration.
- NPV and IRR use equally spaced periods. They are not XNPV/XIRR and do not infer dates.
- CAGR is an endpoint statistic. It does not encode volatility, drawdowns, deposits, withdrawals, taxes, fees or inflation.
- DCF is a mechanical present-value calculation. It does not validate forecast quality, capital structure, discount-rate selection, terminal-growth assumptions or enterprise-to-equity adjustments.
- No market-data retrieval, security selection, forecasting, brokerage integration or order execution is included.

## Verification

The focused test suite covers known-value examples, input validation, time-zero cash-flow convention, IRR convergence and rejection of ambiguous multiple-root cash flows, and terminal-value discounting.

## Integration sequence

1. Keep this module independent of external data providers.
2. Add a typed finance-research adapter that binds source dataset IDs, as-of dates, currency, units and statement periods to these primitives.
3. Add point-in-time data snapshots and restatement/version tracking before historical strategy evaluation.
4. Add independently reproducible scenario and sensitivity analysis.
5. Connect eligible mathematical structures to `preview_transfers`; every transfer remains a hypothesis until paired held-out benchmarks and independent review.
