"""Shared mathematical method policy and bounded, model-conditional references.

No experiment dispatch, model training, proof attestation or promotion occurs.
The finite reference calculations illustrate mathematics, not measured agent gains.
"""
from __future__ import annotations
from fractions import Fraction
import math
from typing import Any, Sequence

POLICY_VERSION = "merlin-mathematical-methods/1"
POLICY_TEXT = """MATHEMATICAL METHOD SELECTION FOR BOTH HERMES ROLES
Consider mathematical and information-theoretic methods across research, coding,
review, training and planning, but use them only when their assumptions fit the
actual task. Record not_applicable when they do not. Preserve the simple baseline.
A mathematical pattern is a candidate mechanism, not evidence of improved agents.

PARRONDO-STYLE STRATEGY SWITCHING
Enumerate bounded, compatible strategies and schedules when a named blockage or
trade-off warrants exploration. Identify the changing state/history, transitions,
common reward, zero baseline, evaluation horizon, reset/carry-over conditions and
switching costs. Specify how one strategy changes conditions for another.
Compare A alone, B alone, fixed/random switching and the current strong baseline
on matched total budgets and independently reset episodes. Keep null and reverse
results. Do not intentionally deploy failing methods merely to invoke a paradox.
Reserve strict Parrondo for evidence that A and B individually lose but their
combination wins under the same declared evaluation; otherwise call a benefit
complementarity or strategy switching. Measure state occupancy and alternatives
before assigning the mechanism. Negative conditional expected increments for every
allowed action at every history cannot yield positive finite-horizon expectation
under integrability; mixing is not a loophole in linearity of expectation.

INFORMATION THEORY AND OTHER MATHEMATICS
Use Bayesian experimental design and expected information gain for selecting tests
that discriminate explicit hypotheses, with prior/likelihood/model provenance and
uncertainty. Information gain is conditional on the supplied model, not truth.
Use information-directed/contextual exploration only with identifiable feedback,
logged selection probabilities, appropriate regret/stationarity assumptions and
cost bounds. Use MDL or rate-distortion ideas only with a declared code/distortion
criterion; compression must preserve required semantics, units and counterexamples.
Use causal interventions/ablations to distinguish mechanisms from correlations.
Use sequential-valid inference for repeated monitoring, or a fixed preregistered
analysis; control multiplicity and do not repeatedly peek at fixed-sample p-values.
Use invariant-preserving transformations, dimensional checks, Pareto constraints
and stability/control arguments where their mathematical premises can be checked.
No method, including simplex/n-ality, is a universal solver or authority bypass.

SHARED LEARNING AND ADOPTION
Hermes proposes schedules/repairs; Hermes Teacher challenges premises, seeks
counterexamples, tests competing explanations and proposes reusable lessons.
Measure each coder and the pair, including accuracy, defect recurrence, false
alarms, cost and collateral regressions. Predeclare minimal benefit and per-agent
noninferiority limits. Freeze development/heldout partitions; do not teach heldout
answers. Adaptive strategy selection requires an evaluation that accounts for it.
A proposed lesson or toy calculation does not change model weights or prompts.
Version and independently approve adoption; preserve rollback and dissent. Neither
coder can approve its own revised work, tests, rubric or verification credentials.
CACE must authenticate the exact artifact/source and the relevant verification
scope through the existing independent trust boundary. Missing isolation,
approval or credentials remains blocked; these methods grant no execution,
compute, merge, deployment, signing or promotion authority."""


def mathematical_strategy_contract() -> dict[str, Any]:
    """Return fresh policy metadata for compiler and teacher request construction."""
    return {"schema": POLICY_VERSION, "instructions": POLICY_TEXT,
            "audience": ["hermes", "hermes-teacher"],
            "application": "conditional_on_fit_and_measured_net_benefit",
            "strict_parrondo_requires": ["state_or_history_mechanism", "matched_objective_and_horizon",
                "standalone_A_negative", "standalone_B_negative", "combined_positive_after_costs",
                "controlled_comparison_and_uncertainty"],
            "automatic_adoption": False, "qualification": False, "promotion_authority": False}


def _fraction(value: Any, label: str) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
        raise ValueError(label + " must be an exact int or Fraction")
    result = Fraction(value)
    if result.numerator.bit_length() > 256 or result.denominator.bit_length() > 256:
        raise ValueError(label + " exceeds the reference arithmetic input bound")
    return result


def stationary_three_state(win_probabilities: Sequence[Fraction]) -> tuple[Fraction, ...]:
    """Stationary distribution for +/-1 movement on residues modulo three.

    State i goes to i+1 with p[i] and i-1 otherwise. Explicit tree weights give
    the normalized stationary distribution; the calculation also checks pi P=pi.
    This is a fixed three-state reference, not a general Markov-chain solver.
    """
    if not isinstance(win_probabilities, (tuple, list)) or len(win_probabilities) != 3:
        raise ValueError("exactly three win probabilities are required")
    p = tuple(_fraction(v, "probability") for v in win_probabilities)
    if any(not 0 <= v <= 1 for v in p):
        raise ValueError("probabilities must lie in [0,1]")
    q = tuple(1-v for v in p)
    weights = (p[2]+q[1]*q[2], q[2]+p[0]*p[2], q[0]+p[0]*p[1])
    total = sum(weights)
    if total <= 0:
        raise ValueError("stationary normalization is singular")
    pi = tuple(v/total for v in weights)
    residual = tuple(pi[(i-1)%3]*p[(i-1)%3] + pi[(i+1)%3]*q[(i+1)%3] - pi[i]
                     for i in range(3))
    if sum(pi) != 1 or any(residual):
        raise ArithmeticError("stationary reference invariant failed")
    return pi


def parrondo_reference(*, epsilon: Fraction = Fraction(1,200),
                       probability_A: Fraction = Fraction(1,2),
                       combined_cost_per_step: Fraction = Fraction(0)) -> dict[str, Any]:
    """Classic capital-mod-3 stationary example, evaluated with rational arithmetic.

    A wins with 1/2-epsilon. B wins with 1/10-epsilon at residue zero and
    3/4-epsilon otherwise. The combination chooses A independently each turn.
    Combined cost is a declared average overhead per turn, not cost per switch.
    """
    e, a, cost = (_fraction(epsilon,"epsilon"), _fraction(probability_A,"probability_A"),
                  _fraction(combined_cost_per_step,"combined_cost_per_step"))
    if not 0 <= e < Fraction(1,10) or not 0 <= a <= 1 or cost < 0:
        raise ValueError("reference epsilon, mixing probability or cost is invalid")
    pa = (Fraction(1,2)-e,)*3
    pb = (Fraction(1,10)-e, Fraction(3,4)-e, Fraction(3,4)-e)
    pc = tuple(a*x+(1-a)*y for x,y in zip(pa,pb))
    results, gains = {}, {}
    for name, probabilities in (("A",pa),("B",pb),("combined",pc)):
        pi = stationary_three_state(probabilities)
        gain = sum(w*(2*p-1) for w,p in zip(pi,probabilities))
        if name == "combined": gain -= cost
        gains[name] = gain
        results[name] = {"stationary_distribution": [str(x) for x in pi],
                         "net_gain_per_step_exact": str(gain), "net_gain_per_step": float(gain)}
    return {"schema": "merlin-parrondo-reference/1", "evidence_class": "exact_model_calculation",
            "model": "capital_mod_3_random_mixture", "epsilon": str(e),
            "probability_A": str(a), "combined_cost_per_step": str(cost), "results": results,
            "strict_parrondo_in_model": gains["A"] < 0 and gains["B"] < 0 and gains["combined"] > 0,
            "agent_benefit_measured": False, "qualification": False, "promotion_authority": False}


def _distribution(values: Any, label: str) -> tuple[float, ...]:
    if not isinstance(values, (list, tuple)) or not 1 <= len(values) <= 64:
        raise ValueError(label + " needs one to sixty-four probabilities")
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not 0 <= v <= 1
           or not math.isfinite(v) for v in values):
        raise ValueError(label + " contains invalid probabilities")
    result = tuple(float(v) for v in values)
    if not math.isclose(math.fsum(result),1.0,rel_tol=0,abs_tol=1e-12):
        raise ValueError(label + " must sum to one; no silent renormalization")
    return result


def expected_information_gain(prior: Sequence[float], likelihoods: Sequence[Sequence[float]],
                              *, cost: float = 1.0, cost_unit: str = "experiment") -> dict[str, Any]:
    """Finite-hypothesis I(H;Y) in bits, conditional on supplied probabilities.

    Rows are P(observation | hypothesis), sharing one observation alphabet.
    A bits/cost ratio is a local diagnostic, not a globally optimal policy.
    """
    p = _distribution(prior,"prior")
    if not isinstance(likelihoods,(list,tuple)) or len(likelihoods) != len(p):
        raise ValueError("one likelihood row per hypothesis is required")
    rows = tuple(_distribution(row,"likelihood") for row in likelihoods)
    n = len(rows[0])
    if any(len(row) != n for row in rows):
        raise ValueError("likelihood rows must share an observation alphabet")
    try:
        valid_cost = not isinstance(cost,bool) and isinstance(cost,(int,float)) and cost > 0 and math.isfinite(cost)
    except OverflowError:
        valid_cost = False
    if not valid_cost:
        raise ValueError("cost must be finite and strictly positive")
    if not isinstance(cost_unit,str) or not cost_unit.strip() or len(cost_unit) > 80:
        raise ValueError("explicit bounded cost_unit is required")
    marginal = tuple(math.fsum(p[i]*rows[i][j] for i in range(len(p))) for j in range(n))
    information = math.fsum(p[i]*rows[i][j]*(math.log2(rows[i][j])-math.log2(marginal[j]))
        for i in range(len(p)) for j in range(n) if p[i]*rows[i][j] > 0)
    entropy = -math.fsum(v*math.log2(v) for v in p if v > 0)
    if information < -1e-10 or information > entropy+1e-10:
        raise ArithmeticError("information calculation exceeded its mathematical bounds")
    information = min(entropy,max(0.0,information))
    per_cost = information/cost
    if not math.isfinite(per_cost):
        raise ValueError("information-per-cost overflow")
    return {"schema": "merlin-finite-eig/1", "expected_information_bits": information,
            "prior_entropy_bits": entropy, "observation_probabilities": list(marginal),
            "expected_bits_per_cost_unit": per_cost, "cost_unit": cost_unit,
            "conditional_on_supplied_model": True, "empirical_validation": "not_assessed",
            "qualification": False, "promotion_authority": False}
