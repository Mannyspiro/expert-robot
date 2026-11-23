"""Choose the smallest falsifiable math or coding tool for a Merlin blockage.

Pure planning only: no execution, network, installs, or authority escalation.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class ToolProposal:
    family: str
    method: str
    input_contract: str
    invariant: str
    falsifier: str
    next_test: str

METHODS = {
    "dependency": ToolProposal("graph", "topological sort / cycle detection", "finite directed edges", "every prerequisite precedes dependent", "cycle or missing prerequisite accepted", "DAG, cycle, missing-node fixtures"),
    "uncertainty": ToolProposal("statistics", "confidence interval and sensitivity analysis", "observations, units, sampling design", "uncertainty and assumptions explicitly tracked", "interval excludes calibrated reference too often", "frozen synthetic calibration and held-out data"),
    "geometry": ToolProposal("linear algebra", "barycentric and affine consistency", "vertices, coordinates, units", "nonnegative simplex weights sum to one", "reconstruction or convex-bound failure", "vertices, edges, degenerate simplex"),
    "search": ToolProposal("combinatorics", "bounded constraint enumeration", "finite factors, constraints, budget", "examined + unexamined covers declared search space", "counts or compatibility violate specification", "tiny exhaustive oracle and truncation"),
    "restart": ToolProposal("state machine", "transition and replay validator", "events, state schema, identities", "no unauthorized transition or silent resume", "interrupted running state resumes automatically", "restart, tamper, and invalid-state tests"),
    "performance": ToolProposal("measurement", "paired baseline benchmark", "frozen workloads and environments", "quality and cost compared on same cases", "claimed improvement vanishes on holdout", "paired runs with confidence intervals"),
}

def propose(blockage: str) -> ToolProposal:
    if not isinstance(blockage, str) or not blockage.strip():
        raise ValueError("nonempty blockage required")
    lower = blockage.lower()
    signals = {
        "dependency": ("dependency", "cycle", "ordering", "prerequisite"),
        "uncertainty": ("uncertainty", "confidence", "variance", "noise"),
        "geometry": ("simplex", "barycentric", "geometry", "affine"),
        "search": ("enumerate", "lacuna", "ideonomy", "combinations"),
        "restart": ("restart", "resume", "checkpoint", "state"),
        "performance": ("latency", "performance", "benchmark", "speed"),
    }
    matches = [family for family, words in signals.items() if any(word in lower for word in words)]
    if len(matches) != 1:
        raise ValueError("ambiguous or unsupported blockage: request a concrete input/output example")
    return METHODS[matches[0]]
