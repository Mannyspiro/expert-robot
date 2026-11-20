"""Enumerate a finite design space for detecting drawing/topology discrepancies."""
from itertools import combinations
import json

from merlin.scientific_loop import enumerate_combination_report

MECHANISMS = ["independent_review", "registered_graph_extraction"]
REPRESENTATIONS = ["named_terminal_graph", "pixel_centreline"]
FALSIFIERS = ["endpoint_swap", "extra_junction"]
groups = [("mechanism", MECHANISMS), ("representation", REPRESENTATIONS), ("falsifier", FALSIFIERS)]
primitives = [{"id": name, "domain": domain, "estimated_cost": costs}
              for domain, values in groups
              for name, costs in zip(values, [1, 2])]
pairs = {frozenset([a["id"], b["id"]]) for a, b in combinations(primitives, 2)
         if a["domain"] != b["domain"]}
report = enumerate_combination_report(
    primitives, pairs, trigger="A plausible illustration can depict a different circuit",
    problem="Detect a semantic wiring discrepancy after raster rendering", limit=64)
report["factor_triples"] = [r for r in report["candidates"] if len(r["primitive_ids"]) == 3]
report["analogy"] = {
    "source": "A transit map can bend every line if stops and transfer stations stay connected.",
    "invariant": "Preserve named terminal adjacency and junction incidence under a change in drawing style.",
    "counterexample": "An overpass and an interchange can paint the same intersecting centreline pixels. The junction mark or an independent terminal graph must disambiguate them.",
    "claim": "A conjecture for judging drawings. Synthetic fixtures are simulations. Program outputs are measurements under the specified fixtures. A graph equality check proves equality only of its two given graphs."
}
print(json.dumps(report, indent=2))
