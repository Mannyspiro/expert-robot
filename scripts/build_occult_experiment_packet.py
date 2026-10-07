#!/usr/bin/env python3
"""Build an end-to-end occult/magic-circle research packet from CRL.

Pipeline:
CRL -> Magick IR -> exact geometry -> ablation plan -> CACE request.

The packet is an experiment specification, never evidence of supernatural
efficacy.
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
geom = load_module(
    "compile_magick_geometry",
    ROOT / "scripts" / "compile_magick_geometry.py",
)


MODEL_CHANNELS = {
    "acoustic_wave": {"acoustic", "vibration", "pressure"},
    "maxwell_em": {"magnetic", "electric", "rf"},
    "magnetostatic": {"magnetic"},
    "heat": {"thermal"},
    "elastic_vibration": {"vibration", "acoustic"},
    "optics": {"optical", "video", "human_report"},
    "fluid": {"pressure", "optical"},
    "chemical": {"chemical", "thermal"},
    "sensor_noise": {
        "magnetic", "electric", "rf", "acoustic", "vibration",
        "optical", "thermal", "pressure", "chemical", "radiation",
        "video", "human_report",
    },
}


def ablation_plan(ir: dict[str, Any]) -> dict[str, Any]:
    axes: list[dict[str, Any]] = []

    primitive_types = {x["type"] for x in ir["geometry"]["primitives"]}
    if "circle" in primitive_types:
        axes.extend([
            {
                "id": "geometry-rotation",
                "channel": "geometry",
                "change": "rotate complete geometry by randomized azimuth",
                "hold_constant": ["materials", "symbol text", "acoustic condition"],
                "question": "Does response track absolute orientation or internal geometry?",
            },
            {
                "id": "geometry-scale",
                "channel": "geometry",
                "change": "apply preregistered uniform scale factors",
                "hold_constant": ["topology", "symbol order"],
                "question": "Does any response obey a quantitative geometric scaling law?",
            },
            {
                "id": "geometry-mirror",
                "channel": "geometry",
                "change": "mirror/chirality reversal where topology permits",
                "hold_constant": ["materials", "timing", "symbol identities"],
                "question": "Is chirality predictive after ordinary field/optical effects are modeled?",
            },
        ])

    topology = " ".join(ir["geometry"].get("topology", [])).lower()
    if "opening" in topology or "break" in topology:
        axes.append({
            "id": "boundary-opening",
            "channel": "topology",
            "change": "open/closed/sham-opening conditions",
            "hold_constant": ["visual appearance where possible", "symbol layout"],
            "question": "Does the boundary break have effects beyond acoustic/airflow/thermal/field boundary conditions?",
        })

    if ir["symbols"]["tokens"]:
        axes.extend([
            {
                "id": "symbol-order",
                "channel": "symbolic_information",
                "change": "permute symbol order while preserving geometry",
                "hold_constant": ["positions", "materials", "overall visual density"],
                "question": "Does ordered symbolic information predict outcomes?",
            },
            {
                "id": "symbol-position",
                "channel": "symbolic_information",
                "change": "swap symbolic identities among fixed positions",
                "hold_constant": ["geometry", "number of marks", "materials"],
                "question": "Does identity-position binding matter independently of geometry?",
            },
        ])

    if ir["acoustics"]["utterances"]:
        axes.extend([
            {
                "id": "semantics-vs-waveform",
                "channel": "acoustic_symbolic",
                "change": "original words, spectral control, altered waveform with same words, recording, silence",
                "hold_constant": ["SPL where applicable", "source position"],
                "question": "Separate semantic/phonetic structure from physical acoustics.",
            },
            {
                "id": "live-vs-recorded",
                "channel": "acoustic_human",
                "change": "live voice versus calibrated playback",
                "hold_constant": ["measured spectrum/SPL as closely as practical"],
                "question": "Does any effect require a live speaker after waveform differences are controlled?",
            },
        ])

    if ir["materials"]:
        axes.append({
            "id": "material-substitution",
            "channel": "materials",
            "change": "historical material versus matched physical-property shams and deliberately mismatched controls",
            "hold_constant": ["geometry", "position", "mass/appearance where feasible"],
            "question": "Which measurable material property, if any, carries the effect?",
        })

    if ir["geometry"].get("orientation_sensitive"):
        axes.append({
            "id": "orientation-reference",
            "channel": "orientation",
            "change": "manuscript-relative, true-north, magnetic-north, randomized azimuth",
            "hold_constant": ["internal geometry"],
            "question": "Does response track geomagnetic/room anisotropy or textual orientation rules?",
        })

    if ir["timing"].get("historical_time_constraints"):
        axes.append({
            "id": "historical-timing",
            "channel": "timing",
            "change": "historical timing metadata versus randomized matched clock times",
            "hold_constant": ["apparatus", "operator procedure"],
            "question": "Does timing add predictive value beyond environmental covariates?",
        })

    if ir["human_actions"]:
        axes.append({
            "id": "observer-removal",
            "channel": "human",
            "change": "observer/operator-present versus automated sensor-only trials",
            "hold_constant": ["apparatus", "recorded stimulus where applicable"],
            "question": "Separate physical sensor effects from perception/expectation/operator coupling.",
        })

    for i, control in enumerate(ir["controls"].get("ablations", [])):
        axes.append({
            "id": f"source-control-{i+1}",
            "channel": "source_declared",
            "change": control,
            "hold_constant": [],
            "question": "Explicit control declared by the CRL source.",
        })

    # Stable deduplication by (channel, change).
    seen = set()
    unique = []
    for axis in axes:
        key = (axis["channel"], axis["change"])
        if key not in seen:
            seen.add(key)
            unique.append(axis)

    return {
        "schema_version": 1,
        "experiment_id": ir["experiment_id"],
        "axes": unique,
        "axis_count": len(unique),
        "selection_policy": "expected_information_gain_then_cost_then_confound_risk",
        "full_factorial_default": False,
        "notes": (
            "Run one-factor and high-information interactions first; promote "
            "to factorial combinations only after a channel survives holdout."
        ),
    }


def cace_request(ir: dict[str, Any], exact: dict[str, Any]) -> dict[str, Any]:
    measured = [m["channel"] for m in ir["measurements"]]
    models = []
    for model in ir["simulation"]["known_physics_models"]:
        channels = sorted(set(measured) & MODEL_CHANNELS.get(model, set()))
        observable = ", ".join(channels) if channels else "declared sensor residual"
        models.append({
            "domain": model,
            "observable": observable,
            "assumptions": [
                "parameters/material properties are measured or provenance-bound",
                "boundary conditions are compiled from the experiment packet",
                "solver convergence alone is not treated as certification",
            ],
            "boundary_conditions": [],
            "materials": ir["materials"],
        })

    return {
        "kind": "cace_magick_request",
        "schema_version": 1,
        "experiment_id": ir["experiment_id"],
        "source_sha256": exact["source_sha256"],
        "exact_geometry": exact,
        "models": models,
        "requested_certificates": [
            "mesh_validity",
            "solver_status",
            "residual",
            "a_posteriori_error",
            "interval_bound",
            "input_identity",
        ],
    }


def build(path: Path) -> dict[str, Any]:
    ir = crl.parse(path.read_text(encoding="utf-8"), str(path))
    exact = geom.compile_magick(ir)
    return {
        "schema_version": 1,
        "source_language": "CRL 0.1",
        "source_file": path.name,
        "magick_ir": ir,
        "exact_geometry": exact,
        "ablation_plan": ablation_plan(ir),
        "cace_request": cace_request(ir, exact),
        "epistemic_status": "experiment_design_not_evidence",
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
