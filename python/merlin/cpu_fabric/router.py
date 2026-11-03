"""Deterministic, conservative specialist activation policy."""
from __future__ import annotations


def choose_modules(task: str, confidence: float, catalog: dict,
                   remaining_budget_bytes: int, min_confidence: float = 0.80) -> dict:
    """Return an explicit route decision; unknown/low-confidence tasks stay core-only."""
    if not 0.0 <= confidence <= 1.0 or not 0.0 <= min_confidence <= 1.0:
        raise ValueError("confidence values must be within [0, 1]")
    if confidence < min_confidence:
        return {"route": "core_only", "modules": [], "reason": "router_confidence_below_threshold"}
    candidates = []
    for module_id, manifest in catalog.items():
        if not getattr(manifest, "approved", False):
            continue
        if task not in getattr(manifest, "task_scope", ()):
            continue
        if getattr(manifest, "estimated_bytes", remaining_budget_bytes + 1) <= remaining_budget_bytes:
            candidates.append((manifest.estimated_bytes, module_id))
    if not candidates:
        return {"route": "core_only", "modules": [], "reason": "no_qualified_affordable_specialist"}
    _, selected = min(candidates)
    return {"route": "core_plus_specialist", "modules": [selected], "reason": "qualified_scope_and_budget_match"}
