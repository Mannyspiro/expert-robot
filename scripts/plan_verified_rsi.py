#!/usr/bin/env python3
"""Plan license-clean, cross-domain RSI experiments from trusted policy and evidence.

Concepts inspired by evolutionary algorithm discovery, reflective feedback,
branching agent lineages and repeatable fixed-budget experiments. This script
does not copy source from those projects, invoke an LLM, execute mutations,
claim measured speedups, certify code or authorize any promotion.

Only the pre-existing trusted promotion workflow can qualify candidates.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import importlib.util
import json
import math
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_estimator():
    spec = importlib.util.spec_from_file_location(
        "verified_rsi_budget_estimator",
        ROOT / "scripts" / "estimate_generation_budget.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("generation budget estimator unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_sha(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()


def metric(value, name, minimum=0.0, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: expected finite numeric value")
    number = float(value)
    if not math.isfinite(number) or number < minimum or (
        maximum is not None and number > maximum
    ):
        raise ValueError(f"{name}: out of allowed range")
    return number


def legal_auto_scope(paths, scope):
    if not paths:
        return False
    for path in paths:
        if not isinstance(path, str) or not path or path.startswith("/"):
            return False
        if any(x in ("..", ".") for x in Path(path).parts):
            return False
        if any(path == x or path.startswith(x)
               for x in scope["forbidden_prefixes"]):
            return False
        if not any(fnmatch.fnmatch(path, pattern)
                   for pattern in scope["allowed_globs"]):
            return False
    return True


def aggregate_feedback(records, routes):
    """At most one observation per route / independent benchmark group.

    Feedback is external task data, never authority to change code.
    Identical lineage copies cannot amplify a result.
    """
    route_ids = {r["id"] for r in routes}
    groups = {}
    for item in records:
        if item["route_id"] not in route_ids:
            raise ValueError("feedback references unregistered RSI route")
        group = item.get("independence_group")
        if not isinstance(group, str) or not group:
            raise ValueError("feedback must declare independent benchmark group")
        artifact = item.get("artifact_sha256")
        if not isinstance(artifact, str) or not re.fullmatch("[a-fA-F0-9]{64}", artifact):
            raise ValueError("feedback requires a SHA256 provenance digest")
        delta = item.get("validation_delta")
        if isinstance(delta, bool) or not isinstance(delta, (int, float)) or (
            not math.isfinite(float(delta)) or not -1.0 <= float(delta) <= 1.0
        ):
            raise ValueError("validation_delta must be finite and in [-1,1]")
        if item.get("holdout_sealed") is not True:
            raise ValueError("unsealed feedback cannot steer RSI search")
        key = (item["route_id"], group)
        if key in groups:
            # Do not treat copied or repeated observations as independent.
            if groups[key]["artifact_sha256"] != artifact:
                raise ValueError("conflicting copied feedback in independence group")
            continue
        groups[key] = item

    by_route = defaultdict(list)
    for (route, _), item in sorted(groups.items()):
        by_route[route].append(item)
    return by_route


def pareto_front(rows):
    """Explore improvements across gain, information, cost and risk."""
    def dominates(a, b):
        good = (
            a["expected_gain"] >= b["expected_gain"]
            and a["information_value"] >= b["information_value"]
            and a["estimated_credits_per_run"] <= b["estimated_credits_per_run"]
            and a["risk"] <= b["risk"]
        )
        strict = (
            a["expected_gain"] > b["expected_gain"]
            or a["information_value"] > b["information_value"]
            or a["estimated_credits_per_run"] < b["estimated_credits_per_run"]
            or a["risk"] < b["risk"]
        )
        return good and strict
    return [a for a in rows if not any(
        dominates(b, a) for b in rows if b is not a
    )]


def plan(catalog, scope, generation_policy, remaining_credits=0,
         feedback=None, max_routes=4):
    if catalog.get("schema_version") != 1 or catalog.get("release_mode") != "plan_only":
        raise ValueError("untrusted or unsupported catalog mode")
    if catalog.get("evidence_rules", {}).get("never_promote_from_planner") is not True:
        raise ValueError("planner policy must forbid automatic promotion")
    if catalog.get("evidence_rules", {}).get("never_execute_from_planner") is not True:
        raise ValueError("planner policy must forbid execution")
    if (scope.get("schema_version") != 1 or
        generation_policy.get("schema_version") != 1):
        raise ValueError("trusted policies must have supported versions")
    if (not isinstance(remaining_credits, int) or isinstance(remaining_credits, bool)
            or not 0 <= remaining_credits <= 1500):
        raise ValueError("explicit remaining Avrea credits must be integer 0..1500")
    if not isinstance(max_routes, int) or not 1 <= max_routes <= 8:
        raise ValueError("max_routes outside planner limits")

    routes = catalog["candidate_routes"]
    if len(routes) != len({r["id"] for r in routes}):
        raise ValueError("RSI route IDs must be unique")
    observations = aggregate_feedback(feedback or [], routes)
    cfg = generation_policy["generation_budget"]
    estimator = load_estimator()

    analyzed = []
    for route in routes:
        expected = metric(route["expected_gain_prior"], "prior_gain", 0, 1)
        variance = metric(route["variance_prior"], "prior_variance", 0, 1)
        risk = metric(route["risk"], "risk", 0, 1)
        information = metric(route["information_value"], "information", 0, 1)
        cost = int(metric(route["estimated_credits_per_run"],
                          "estimated_credits_per_run", 1, 1500))
        if route["estimated_credits_per_run"] != cost:
            raise ValueError("credits per run must be integer")
        records = observations[route["id"]]
        independent_count = len(records)
        if records:
            # Shrink noisy, unverified benchmark observations toward the prior
            # rather than calling them real gains.
            deltas = [float(item["validation_delta"]) for item in records]
            mean = sum(deltas) / len(deltas)
            expected = max(0.0, min(1.0,
                (expected * 3.0 + max(-0.5, min(0.5, mean)) * len(deltas))
                / (3.0 + len(deltas))
            ))
            variance = max(variance,
                sum((x - mean)**2 for x in deltas) / max(1, len(deltas)))
        estimated = estimator.estimate(
            expected, variance, max(0.01, cost / 100),
            metric(cfg["default_diminishing_rate"], "diminishing_rate", 0, 0.99),
            metric(cfg["information_weight"], "information_weight", 0),
            metric(cfg["cost_weight"], "cost_weight", 0),
            cfg["min_runs"], cfg["max_runs"],
        )
        feedback_digest = canonical_sha([
            {k: item.get(k) for k in (
                "route_id","independence_group","artifact_sha256",
                "validation_delta","holdout_sealed"
            )}
            for item in records
        ])
        score = (
            0.47 * expected + 0.33 * information
            - 0.12 * risk - 0.08 * (cost / 100)
        )
        analyzed.append({
            "route_id": route["id"], "domain": route["domain"],
            "title": route["title"],
            "diversity_group": route["diversity_group"],
            "expected_gain": expected, "variance": variance,
            "risk": risk, "information_value": information,
            "estimated_credits_per_run": cost,
            "recommended_runs_unconstrained": estimated["recommended_runs"],
            "estimated_candidate_score": score,
            "independent_feedback_groups": independent_count,
            "feedback_digest_sha256": feedback_digest,
            "empirical_gain_verified": False,
            "license_reuse": "ideas_only_no_upstream_code_copied",
            "auto_scope_paths_plausible": legal_auto_scope(
                route["target_paths"], scope),
            "candidate_target_paths": route["target_paths"],
            "evaluation_suites": route["test_suites"],
            "formal_required": route["formal_required"],
            "inspiration": route["model"],
            "failure_feedback_to_analyze": route["failure_feedback"],
            "next_stage": "DESIGN_CANDIDATE_AND_INDEPENDENT_EVALUATION",
            "promotion_status": "NOT_AUTHORIZED",
        })

    frontier = pareto_front(analyzed)
    frontier_ids = {x["route_id"] for x in frontier}
    for row in analyzed:
        row["pareto_frontier"] = row["route_id"] in frontier_ids

    # Favour diversity before spending the entire small budget on one niche.
    ordered = sorted(
        analyzed,
        key=lambda x: (
            not x["pareto_frontier"],
            -x["estimated_candidate_score"], x["route_id"]
        )
    )
    picked = []
    picked_ids = set()
    diversity_seen = set()
    for route in ordered:
        if len(picked) >= max_routes:
            break
        if route["diversity_group"] not in diversity_seen:
            picked.append(route)
            picked_ids.add(route["route_id"])
            diversity_seen.add(route["diversity_group"])
    for route in ordered:
        if len(picked) >= max_routes:
            break
        if route["route_id"] not in picked_ids:
            picked.append(route)
            picked_ids.add(route["route_id"])

    available = remaining_credits
    allocations = []
    min_runs = generation_policy["generation_budget"]["min_runs"]
    for route in picked:
        requested = route["recommended_runs_unconstrained"]
        affordable = available // route["estimated_credits_per_run"]
        runs = min(requested, affordable)
        if runs < min_runs:
            runs = 0
        credits = runs * route["estimated_credits_per_run"]
        available -= credits
        allocations.append({
            **route,
            "planned_runs": runs,
            "reserved_credits_if_executed": credits,
            "execution_authorized": False,
            "reason": (
                "candidate research plan only; independent collar/evaluator required"
                if runs >= min_runs else
                "not enough budget for minimum statistically useful run count"
            ),
        })
    return {
        "schema_version": 1,
        "program": catalog["program"],
        "source_catalog_sha256": canonical_sha(catalog),
        "feedback_records_received": len(feedback or []),
        "remaining_avrea_credits_supplied": remaining_credits,
        "modelled_max_credit_reservation": remaining_credits - available,
        "credits_unallocated": available,
        "account_wide_remaining_credits_verified": False,
        "ranked_routes": sorted(analyzed, key=lambda x: (
            -x["estimated_candidate_score"], x["route_id"])),
        "pareto_route_ids": sorted(frontier_ids),
        "diversity_selected_plans": allocations,
        "lineages_promoted": 0,
        "candidate_code_executed": False,
        "automatic_promotion_authorized": False,
        "eval_boundary": "Existing independent collared RSI qualification and promotion workflows only",
        "epistemic_status": "planning_priors_not_measured_capability_improvements",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", type=Path,
                   default=ROOT/"config"/"verified_rsi_integration_catalog.json")
    p.add_argument("--scope", type=Path,
                   default=ROOT/"config"/"auto_promotion_scope.json")
    p.add_argument("--experiment-policy", type=Path,
                   default=ROOT/"config"/"experiment_policy.json")
    p.add_argument("--feedback", type=Path)
    p.add_argument("--remaining-avrea-credits", type=int, default=0)
    p.add_argument("--max-routes", type=int, default=4)
    p.add_argument("-o", "--output", type=Path)
    args = p.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    scope = json.loads(args.scope.read_text(encoding="utf-8"))
    policy = json.loads(args.experiment_policy.read_text(encoding="utf-8"))
    feedback = json.loads(args.feedback.read_text(encoding="utf-8")) if args.feedback else []
    result = plan(catalog, scope, policy,
                  args.remaining_avrea_credits, feedback, args.max_routes)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(json.dumps({
        "program": result["program"],
        "selected": [
            {"route_id":x["route_id"],"planned_runs":x["planned_runs"],
             "auto_scope_paths_plausible":x["auto_scope_paths_plausible"]}
            for x in result["diversity_selected_plans"]
        ],
        "remaining_credits_unallocated": result["credits_unallocated"],
        "promotion_authorized": result["automatic_promotion_authorized"],
        "evidence_file":str(args.output) if args.output else None,
    },sort_keys=True))


if __name__ == "__main__":
    main()
