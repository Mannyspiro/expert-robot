"""Convert the legacy 0.2 tranche into canonical, schema-validated entries.

The converter preserves dimensions and legacy conditions, and deliberately
sets evidence_status=UNVERIFIED. A citation identifier is not silently upgraded
into a verified source claim.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
ATLAS = ROOT / "docs/research/real-world-equation-atlas"
LEGACY = ATLAS / "NORMALIZED_ENTRIES_001-020.json"
BATCH_021_030 = ATLAS / "NORMALIZED_ENTRIES_021-030.json"
BATCH_031_040 = ATLAS / "NORMALIZED_ENTRIES_031-040.json"
SCHEMA = ATLAS / "equation-entry.schema.json"
OUTPUT = ATLAS / "NORMALIZED_ENTRIES_001-040_V0.3.json"

MODEL_FAMILY = {
    "optimization": "mathematical_optimization",
    "estimation": "statistical_estimation",
    "inference": "probabilistic_inference",
    "decision": "decision_optimization",
    "linear algebra": "linear_operator",
    "statistics": "statistical_moments",
    "networks": "graph_theory",
    "geometry": "computational_geometry",
    "robotics": "rigid_body_geometry",
    "numerical analysis": "numerical_analysis",
}

def normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    assumptions = list(entry.get("assumptions", []))
    conditions = entry.get("conditions", [])
    assumptions.extend(f"Condition: {item}" for item in conditions)
    variables = []
    for variable in entry.get("variables", []):
        normalized = {
            "symbol": variable["symbol"],
            "meaning": variable["meaning"],
            "unit": variable["unit"],
        }
        if "dimension" in variable:
            normalized["dimension"] = variable["dimension"]
        if "domain" in variable:
            normalized["domain"] = variable["domain"]
        variables.append(normalized)

    source_ids = entry.get("sources", [])
    sources = [
        {
            "claim": "Legacy source-register reference; claim-level support still requires review.",
            "citation": source_id,
            "doi_or_url": None,
        }
        for source_id in source_ids
    ]
    regime = "; ".join(conditions) if conditions else (
        "Application-specific validity regime has not yet been fully specified."
    )
    return {
        "id": entry["id"],
        "domain": entry["domain"],
        "application": "General mathematical formulation; application-specific instance not yet specified.",
        "model_family": MODEL_FAMILY.get(entry["domain"], "unspecified_model_family"),
        "equations": [entry["equation"]],
        "variables": variables,
        "assumptions": assumptions,
        "initial_conditions": None,
        "boundary_conditions": None,
        "validity_regime": regime,
        "intuition": "",
        "applications": [],
        "limitations": ["Legacy tranche does not yet provide a complete application-specific limitation analysis."],
        "alternatives": [],
        "validation": [],
        "uncertainty": [],
        "formal_claims": [],
        "sources": sources,
        "evidence_status": "UNVERIFIED",
        "confidence_rationale": (
            "Migrated from legacy normalized metadata. Source identifiers are preserved, "
            "but entry-specific source passages, application assumptions, and independent "
            "validation have not yet been audited."
        ),
    }

def main() -> int:
    legacy = json.loads(LEGACY.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    entries = [normalize_entry(entry) for entry in legacy["entries"]]
    batch_021_030 = json.loads(BATCH_021_030.read_text(encoding="utf-8"))
    entries.extend(batch_021_030["entries"])
    batch_031_040 = json.loads(BATCH_031_040.read_text(encoding="utf-8"))
    entries.extend(batch_031_040["entries"])
    ids = [entry["id"] for entry in entries]
    if len(ids) != len(set(ids)):
        raise SystemExit("Duplicate equation IDs in normalized batches")
    if ids != sorted(ids):
        raise SystemExit("Equation entries must be ordered by stable ID")
    errors = []
    for entry in entries:
        errors.extend(
            f"{entry['id']}: {error.message}"
            for error in validator.iter_errors(entry)
        )
    if errors:
        raise SystemExit("\n".join(errors))
    result = {
        "schema_version": "0.3",
        "dimension_basis": legacy["dimension_basis"],
        "migration_policy": "Legacy entries are normalized and canonical batch entries are preserved; evidence remains UNVERIFIED until claim-level review.",
        "entries": entries,
    }
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"PASS canonical schema: {len(entries)} entries -> {OUTPUT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
