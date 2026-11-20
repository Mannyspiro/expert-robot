"""Enumerate registered schematic hypotheses in a finite compatibility catalogue."""
from itertools import combinations
import json
from merlin.scientific_loop import enumerate_combination_report

factors = {
    "mechanism": ["reference_ink_residual", "terminal_seed_connectivity"],
    "representation": ["binary_mask_components", "terminal_partition"],
    "falsifier": ["unexpected_cross_net_bridge", "scan_gap_near_crossing"],
}
primitives = [{"id": name, "domain": factor, "estimated_cost": i + 1}
              for factor, names in factors.items() for i, name in enumerate(names)]
compatible = {frozenset([a["id"],b["id"]]) for a,b in combinations(primitives,2)
              if a["domain"] != b["domain"]}
ret = enumerate_combination_report(primitives,compatible,trigger="A mistaken all-pass reviewer can qualify added ink",
    problem="Govern a claimed unchanged registered drawing with independent physical evidence",limit=64)
ret["missing_capability"] = "Withhold a changed or ambiguous registered schematic with a mistaken all-pass verdict."
ret["analogy"] = {
    "source": "Two dye injections in adjacent sealed microfluidic channels.",
    "invariant": "The partition of accessible endpoints under a change in visual appearance.",
    "counterexample": "Dye crossing beneath another channel at a different depth can overlap in a photograph without sharing fluid.",
    "status": "Analogy and method are conjectures. Drawn candidate fixtures are simulations. Counts and times are measurements. Connected components prove reachability in the given mask only."
}
ret["three_factor_cases"]=[x for x in ret["candidates"] if len(x["primitive_ids"])==3]
print(json.dumps(ret,indent=2))
