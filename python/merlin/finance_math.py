"""Deterministic, dependency-free financial mathematics primitives.

These functions calculate transparent cash-flow and growth measures. They do
not fetch market data, forecast returns, recommend securities, or authorize
financial transactions. Inputs are assumed to be already validated and
appropriately dated by the calling research adapter.
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def cagr(beginning_value: float, ending_value: float, years: float) -> float:
    """Return compound annual growth rate as a decimal fraction.

    Both endpoint values must be positive. This endpoint statistic does not
    describe volatility, interim drawdowns, or external cash flows.
    """
    beginning = _finite(beginning_value, "beginning_value")
    ending = _finite(ending_value, "ending_value")
    duration = _finite(years, "years")
    if beginning <= 0 or ending <= 0:
        raise ValueError("beginning_value and ending_value must be positive")
    if duration <= 0:
        raise ValueError("years must be positive")
    return math.expm1(math.log(ending / beginning) / duration)


def total_return(beginning_value: float, ending_value: float) -> float:
    """Return simple endpoint total return as a decimal fraction."""
    beginning = _finite(beginning_value, "beginning_value")
    ending = _finite(ending_value, "ending_value")
    if beginning <= 0:
        raise ValueError("beginning_value must be positive")
    return ending / beginning - 1.0


def npv(rate: float, cash_flows: Iterable[float]) -> float:
    """Return NPV with the first cash flow at period zero."""
    discount = _finite(rate, "rate")
    if discount <= -1:
        raise ValueError("rate must be greater than -1")
    flows = tuple(_finite(value, "cash_flow") for value in cash_flows)
    if not flows:
        raise ValueError("cash_flows must not be empty")
    return math.fsum(value / ((1.0 + discount) ** period)
                     for period, value in enumerate(flows))


def irr(cash_flows: Sequence[float], *, tolerance: float = 1e-10,
        max_iterations: int = 256) -> float:
    """Solve periodic IRR by bisection for conventional one-sign-change flows.

    Requiring exactly one sign change avoids silently selecting one of several
    possible roots for non-conventional cash flows. The first flow is at t=0.
    """
    flows = tuple(_finite(value, "cash_flow") for value in cash_flows)
    if len(flows) < 2:
        raise ValueError("at least two cash flows are required")
    signs = [1 if value > 0 else -1 for value in flows if value != 0]
    if len(signs) < 2 or sum(a != b for a, b in zip(signs, signs[1:])) != 1:
        raise ValueError("cash flows must contain exactly one sign change")
    tol = _finite(tolerance, "tolerance")
    if tol <= 0 or isinstance(max_iterations, bool) or max_iterations < 1:
        raise ValueError("tolerance and max_iterations must be positive")

    low, high = -0.999999999, 1.0
    f_low = npv(low, flows)
    f_high = npv(high, flows)
    while f_low * f_high > 0 and high < 1e12:
        high = high * 2.0 + 1.0
        f_high = npv(high, flows)
    if f_low == 0:
        return low
    if f_high == 0:
        return high
    if f_low * f_high > 0:
        raise ValueError("could not bracket an IRR root")

    for _ in range(max_iterations):
        middle = (low + high) / 2.0
        f_middle = npv(middle, flows)
        if abs(f_middle) <= tol or (high - low) <= tol:
            return middle
        if f_low * f_middle <= 0:
            high, f_high = middle, f_middle
        else:
            low, f_low = middle, f_middle
    raise ArithmeticError("IRR solver did not converge within max_iterations")


def discounted_cash_flow(cash_flows: Sequence[float], discount_rate: float,
                         terminal_value: float = 0.0) -> dict[str, float]:
    """Return explicit-period PV, terminal PV and total enterprise-value proxy.

    cash_flows contains forecast period 1..N (there is no t=0 flow here).
    terminal_value is placed at period N. This is a mechanical valuation
    calculation, not a complete enterprise valuation or investment opinion.
    """
    rate = _finite(discount_rate, "discount_rate")
    terminal = _finite(terminal_value, "terminal_value")
    if rate <= -1:
        raise ValueError("discount_rate must be greater than -1")
    flows = tuple(_finite(value, "cash_flow") for value in cash_flows)
    if not flows:
        raise ValueError("cash_flows must not be empty")
    explicit_pv = math.fsum(value / ((1.0 + rate) ** period)
                            for period, value in enumerate(flows, start=1))
    terminal_pv = terminal / ((1.0 + rate) ** len(flows))
    return {
        "explicit_cash_flow_pv": explicit_pv,
        "terminal_value_pv": terminal_pv,
        "total_value": explicit_pv + terminal_pv,
    }
