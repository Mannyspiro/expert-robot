#!/usr/bin/env python3
"""Build a CACE alchemy/material-transformation experiment packet from CRL.

This compiler preserves historical/process semantics while refusing to invent
modern chemical identities, masses, temperatures, or reaction mechanisms.
Unknowns remain unresolved and hazardous operations remain simulation-first.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


crl = load_module("compile_crl", ROOT / "scripts" / "compile_crl.py")


def ordered_processes(ir: dict[str, Any]) -> list[dict[str, Any]]:
    rows = list(ir.get("processes", []))
    if not rows:
        raise ValueError("alchemy route requires PROCESS directives")

    indexed = []
    for i, row in enumerate(rows):
        order = row.get("order_index")
        if order is None:
            raise ValueError(f"process {row['id']!r} requires explicit order")
        indexed.append((int(order), i, row))

    indexed.sort()
    orders = [x[0] for x in indexed]
    if len(orders) != len(set(orders)):
        raise ValueError("process order indices must be unique")

    return [x[2] for x in indexed]


def process_graph(ir: dict[str, Any]) -> dict[str, Any]:
    rows = ordered_processes(ir)
    nodes = []
    edges = []

    energies = {x["id"]: x for x in ir.get("energy_inputs", [])}
    materials = {x["id"] for x in ir.get("materials", [])}

    for i, row in enumerate(rows):
        missing_targets = [t for t in row["targets"] if t not in materials]
        # Targets may also refer to prior process products that are not yet
        # represented as named materials. Preserve rather than guess identity.
        unresolved = list(missing_targets)

        eref = row.get("energy_ref")
        if eref is not None and eref not in energies:
            raise ValueError(
                f"process {row['id']!r} references unknown energy source {eref!r}"
            )

        nodes.append({
            "id": row["id"],
            "order_index": row["order_index"],
            "kind": row["kind"],
            "targets": row["targets"],
            "energy_ref": eref,
            "simulation_only": bool(row.get("simulation_only", True)),
            "parameters": row.get("parameters", {}),
            "unresolved_target_identities": unresolved,
            "historical_label": row.get("historical_label"),
        })

        if i:
            edges.append({
                "from": rows[i - 1]["id"],
                "to": row["id"],
                "relation": "precedes",
            })

    return {
        "schema_version": 1,
        "nodes": nodes,
        "edges": edges,
        "acyclic_by_construction": True,
    }


def ledger(ir: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mass_balance": {
            "status": "UNRESOLVED_UNLESS_INPUT_OUTPUT_MASSES_ARE_SUPPLIED",
            "rule": "never infer missing mass values or historical substance identity",
        },
        "energy_balance": {
            "declared_sources": [
                {
                    "id": e["id"],
                    "kind": e["kind"],
                    "measured": e["measured"],
                    "profile": e["profile"],
                }
                for e in ir.get("energy_inputs", [])
            ],
            "status": (
                "MEASURED_INPUTS_REQUIRED_FOR_QUANTITATIVE_BALANCE"
                if ir.get("energy_inputs")
                else "NO_EXPLICIT_ENERGY_SOURCE"
            ),
        },
        "identity_policy": (
            "Historical substance names/descriptions remain provenance labels "
            "until independently mapped to a modern composition."
        ),
    }


def cace_request(ir: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    domains = [
        x for x in ir["simulation"]["known_physics_models"]
        if x in {"heat", "fluid", "chemical", "optics", "sensor_noise"}
    ]
    if not domains:
        raise ValueError("alchemy route requires at least one compatible model")

    return {
        "kind": "cace_alchemy_request",
        "schema_version": 1,
        "experiment_id": ir["experiment_id"],
        "materials": ir["materials"],
        "energy_inputs": ir.get("energy_inputs", []),
        "process_graph": graph,
        "models": domains,
        "measurements": ir["measurements"],
        "requested_certificates": [
            "solver_status",
            "residual",
            "a_posteriori_error",
            "interval_bound",
            "input_identity",
        ],
        "evidence_ceiling": "known_physics_model_result_not_transmutation_claim",
    }


def build(path: Path) -> dict[str, Any]:
    ir = crl.parse(path.read_text(encoding="utf-8"), str(path))
    graph = process_graph(ir)
    return {
        "schema_version": 1,
        "source_language": "CRL 0.1",
        "source_file": path.name,
        "magick_ir": ir,
        "process_graph": graph,
        "mass_energy_ledger": ledger(ir),
        "cace_request": cace_request(ir, graph),
        "epistemic_status": "material_process_experiment_design_not_evidence",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("input", type=Path)
    p.add_argument("-o", "--output", type=Path)
    args = p.parse_args()
    result = build(args.input)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
