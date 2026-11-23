#!/usr/bin/env python3
"""Compile CACE Ritual Language (.crl) into Magick IR v0.1.

CRL is intentionally small and auditable. It is a research protocol language,
not an assertion that historical supernatural claims are physically real.

Design rules:
- symbolic text and acoustic waveform are separate channels;
- historical provenance is mandatory;
- missing witness pixels are never reconstructed;
- unknown channels are residual hypotheses, never explanations;
- controls and measurements compile alongside the ritual description;
- output is deterministic JSON suitable for Magick IR/CACE tooling.
"""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any


class CRLError(ValueError):
    pass


def atom(value: str) -> Any:
    low = value.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low == "null":
        return None
    if "/" in value:
        # Preserve exact rational syntax for the exact-geometry compiler.
        parts = value.split("/")
        if len(parts) == 2:
            try:
                int(parts[0]); int(parts[1])
                return value
            except ValueError:
                pass
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def vec3(text: str) -> list[Any]:
    parts = text.split(",")
    if len(parts) != 3:
        raise CRLError(f"expected x,y,z vector, got {text!r}")
    return [atom(x) for x in parts]


def vertices(text: str) -> list[list[Any]]:
    rows = [row for row in text.split(";") if row]
    if len(rows) < 3:
        raise CRLError("polygon requires at least three semicolon-separated vertices")
    return [vec3(row) for row in rows]


def split_args(tokens: list[str]) -> tuple[list[str], dict[str, str]]:
    positional: list[str] = []
    kwargs: dict[str, str] = {}
    for token in tokens:
        if "=" in token:
            key, value = token.split("=", 1)
            if not key:
                raise CRLError(f"invalid option {token!r}")
            kwargs[key] = value
        else:
            positional.append(token)
    return positional, kwargs


def required(mapping: dict[str, str], name: str, context: str) -> str:
    if name not in mapping:
        raise CRLError(f"{context}: missing required {name}=...")
    return mapping[name]


def new_ir() -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "experiment_id": None,
        "title": None,
        "source": {
            "tradition": None,
            "witnesses": [],
            "transmission_policy": {
                "copied_observations_count_once": True,
                "locus_cap": 1,
                "missing_pixels_policy": "latent_no_reconstruction",
            },
        },
        "claim": {
            "historical_description": "",
            "portal_class": "P0_perceptual",
            "evidence_ceiling": "historical_only",
            "predicted_observables": [],
        },
        "geometry": {
            "primitives": [],
            "topology": [],
            "coordinate_frame": "laboratory Cartesian xyz, meters",
            "symmetry_group": None,
            "orientation_sensitive": False,
        },
        "symbols": {"tokens": [], "relations": []},
        "acoustics": {"utterances": []},
        "materials": [],
        "orientation": {
            "reference": "manuscript_relative",
            "azimuth_deg": None,
            "inclination_deg": None,
            "astronomical_context": None,
        },
        "timing": {
            "sequence": [],
            "relative_timestamps_s": [],
            "historical_time_constraints": [],
        },
        "environment": {
            "temperature_c": None,
            "pressure_pa": None,
            "relative_humidity": None,
            "ambient_em": None,
            "ambient_acoustic": None,
            "lighting": None,
        },
        "human_actions": [],
        "measurements": [],
        "controls": {
            "ablations": [],
            "blinding": "none",
            "randomization": False,
            "preregistered": False,
            "holdout_fraction": 0.0,
        },
        "simulation": {
            "known_physics_models": [],
            "cace_pipeline": [
                "exact geometry reconstruction",
                "mesh validation",
                "coordinate/shape functions",
                "sparse operator assembly",
                "solver",
                "residual",
                "a-posteriori error estimator",
                "interval/certified bound",
                "adaptive refinement",
                "certificate",
            ],
            "residual_policy": {
                "compare_observed_to_interval_bound": True,
                "anomaly_requires_bound_exceedance": True,
                "multiple_testing_correction": "preregistered family-wise or false-discovery control",
            },
        },
        "evidence": {
            "status": "UNTESTED",
            "replications": 0,
            "independent_labs": 0,
            "known_physics_excluded": False,
            "notes": "Compiled from CRL; no physical efficacy is asserted.",
        },
        "unknown_channels": [],
        "parameters": [],
        "bindings": [],
        "energy_inputs": [],
        "processes": [],
        "historical_loci": [],
    }


def parse(text: str, source_name: str = "<memory>") -> dict[str, Any]:
    ir = new_ir()
    seen_header = False
    seen_end = False
    ids: set[str] = set()

    for line_no, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue

        try:
            tokens = shlex.split(stripped, comments=True, posix=True)
        except ValueError as exc:
            raise CRLError(f"{source_name}:{line_no}: {exc}") from exc
        if not tokens:
            continue

        op = tokens[0].upper()
        args = tokens[1:]
        pos, kw = split_args(args)
        ctx = f"{source_name}:{line_no}:{op}"

        if op == "RITUAL":
            if seen_header:
                raise CRLError(f"{ctx}: duplicate RITUAL header")
            if pos != ["0.1"]:
                raise CRLError(f"{ctx}: expected 'RITUAL 0.1'")
            seen_header = True
            continue

        if not seen_header:
            raise CRLError(f"{ctx}: RITUAL 0.1 must be first directive")

        if op == "END":
            seen_end = True
            break

        if op == "ID":
            if len(pos) != 1:
                raise CRLError(f"{ctx}: ID requires one token")
            ir["experiment_id"] = pos[0]

        elif op == "TITLE":
            if not pos:
                raise CRLError(f"{ctx}: TITLE requires text")
            ir["title"] = " ".join(pos)

        elif op == "TRADITION":
            if not pos:
                raise CRLError(f"{ctx}: TRADITION requires text")
            ir["source"]["tradition"] = " ".join(pos)

        elif op == "LOCUS_CAP":
            if len(pos) != 1:
                raise CRLError(f"{ctx}: LOCUS_CAP requires integer")
            ir["source"]["transmission_policy"]["locus_cap"] = int(pos[0])

        elif op == "WITNESS":
            if len(pos) != 1:
                raise CRLError(f"{ctx}: WITNESS requires witness id")
            wid = pos[0]
            ir["source"]["witnesses"].append({
                "id": wid,
                "kind": required(kw, "kind", ctx),
                "shelfmark": kw.get("shelfmark"),
                "folio": kw.get("folio"),
                "date": kw.get("date"),
                "provenance_status": required(kw, "provenance", ctx),
                "independence_weight": float(kw.get("weight", "1")),
                "visual_features_imputed": False,
                "notes": kw.get("notes", ""),
            })

        elif op == "LOCUS":
            if len(pos) != 1:
                raise CRLError(f"{ctx}: LOCUS requires locus id")
            witness_refs = required(kw, "witnesses", ctx).split(",")
            ir["historical_loci"].append({
                "id": pos[0],
                "feature_class": required(kw, "feature", ctx),
                "channel": required(kw, "channel", ctx),
                "witness_refs": witness_refs,
                "observed_state": required(kw, "state", ctx),
                "confidence": float(kw.get("confidence", "1")),
                "independence_group": required(kw, "group", ctx),
                "evidence_status": kw.get("status", "observed"),
                "experimental_target": kw.get("target"),
                "notes": kw.get("notes", ""),
            })

        elif op == "CLAIM":
            if len(pos) < 3:
                raise CRLError(
                    f"{ctx}: CLAIM syntax is CLAIM <P0..P4 class> <evidence ceiling> \"description\""
                )
            ir["claim"]["portal_class"] = pos[0]
            ir["claim"]["evidence_ceiling"] = pos[1]
            ir["claim"]["historical_description"] = " ".join(pos[2:])

        elif op == "PREDICT":
            if not pos:
                raise CRLError(f"{ctx}: PREDICT requires observable text")
            ir["claim"]["predicted_observables"].append(" ".join(pos))

        elif op == "PARAM":
            if len(pos) != 1:
                raise CRLError(f"{ctx}: PARAM requires parameter id")
            values = None
            if "values" in kw:
                values = [atom(x) for x in kw["values"].split(",") if x != ""]
            ir["parameters"].append({
                "id": pos[0],
                "kind": required(kw, "kind", ctx),
                "semantic_role": required(kw, "role", ctx),
                "values": values,
                "minimum": atom(kw["min"]) if "min" in kw else None,
                "maximum": atom(kw["max"]) if "max" in kw else None,
                "units": kw.get("units"),
                "provenance_ref": kw.get("provenance"),
                "notes": kw.get("notes", ""),
            })

        elif op == "BIND":
            if len(pos) != 1:
                raise CRLError(f"{ctx}: BIND requires target path")
            ir["bindings"].append({
                "parameter": required(kw, "parameter", ctx),
                "target": pos[0],
                "mode": kw.get("mode", "direct"),
                "transform": kw.get("transform"),
                "notes": kw.get("notes", ""),
            })

        elif op in {"POINT", "LINE", "CIRCLE", "SPHERE", "POLYGON", "GLYPH_PATH"}:
            if len(pos) != 1:
                raise CRLError(f"{ctx}: geometry directive requires one id")
            gid = pos[0]
            if gid in ids:
                raise CRLError(f"{ctx}: duplicate id {gid!r}")
            ids.add(gid)
            kind = op.lower()
            if op == "GLYPH_PATH":
                kind = "glyph_path"

            params: dict[str, Any] = {}
            if op == "POINT":
                params["xyz_m"] = vec3(required(kw, "xyz", ctx))
            elif op == "LINE":
                params["point"] = vec3(required(kw, "point", ctx))
                params["direction"] = vec3(required(kw, "direction", ctx))
            elif op in {"CIRCLE", "SPHERE"}:
                params["center"] = vec3(required(kw, "center", ctx))
                params["radius_m"] = atom(required(kw, "radius", ctx))
                if op == "CIRCLE":
                    params["normal"] = vec3(required(kw, "normal", ctx))
            elif op == "POLYGON":
                params["vertices"] = vertices(required(kw, "vertices", ctx))
            elif op == "GLYPH_PATH":
                params["points"] = vertices(required(kw, "points", ctx))

            uncertainty = None
            if "uncertainty" in kw:
                uncertainty = {"declared": atom(kw["uncertainty"])}

            ir["geometry"]["primitives"].append({
                "type": kind,
                "id": gid,
                "parameters": params,
                "uncertainty": uncertainty,
            })

        elif op == "TOPOLOGY":
            if not pos:
                raise CRLError(f"{ctx}: TOPOLOGY requires a relation")
            ir["geometry"]["topology"].append(" ".join(pos))

        elif op == "FRAME":
            if not pos:
                raise CRLError(f"{ctx}: FRAME requires text")
            ir["geometry"]["coordinate_frame"] = " ".join(pos)

        elif op == "SYMMETRY":
            ir["geometry"]["symmetry_group"] = " ".join(pos) if pos else None

        elif op == "ORIENTATION_SENSITIVE":
            if len(pos) != 1:
                raise CRLError(f"{ctx}: expected true or false")
            ir["geometry"]["orientation_sensitive"] = bool(atom(pos[0]))

        elif op == "SYMBOL":
            if len(pos) != 1:
                raise CRLError(f"{ctx}: SYMBOL requires symbol id")
            sid = pos[0]
            if sid in ids:
                raise CRLError(f"{ctx}: duplicate id {sid!r}")
            ids.add(sid)
            ir["symbols"]["tokens"].append({
                "id": sid,
                "kind": required(kw, "kind", ctx),
                "text": required(kw, "text", ctx),
                "semantic_role": required(kw, "role", ctx),
                "language": kw.get("language"),
                "diplomatic_form": kw.get("diplomatic"),
                "normalized_form": kw.get("normalized"),
                "position_ref": kw.get("position"),
                "order_index": int(kw["order"]) if "order" in kw else None,
                "repetitions": int(kw.get("repeat", "1")),
                "confidence": float(kw.get("confidence", "1")),
                "provenance_ref": kw.get("provenance"),
                "notes": kw.get("notes", ""),
            })

        elif op == "SYMBOL_REL":
            relation = required(kw, "relation", ctx)
            members = required(kw, "members", ctx).split(",")
            if len(members) < 2:
                raise CRLError(f"{ctx}: members requires two or more ids")
            ir["symbols"]["relations"].append({
                "relation": relation,
                "members": members,
                "confidence": float(kw.get("confidence", "1")),
            })

        elif op == "VOICE":
            if len(pos) != 1:
                raise CRLError(f"{ctx}: VOICE requires symbolic token id")
            ir["acoustics"]["utterances"].append({
                "token": pos[0],
                "mode": required(kw, "mode", ctx),
                "phonetic_transcription": kw.get("phonetic"),
                "waveform_ref": kw.get("waveform"),
                "target_spl_db": float(kw["spl"]) if "spl" in kw else None,
                "fundamental_hz": float(kw["f0"]) if "f0" in kw else None,
                "phase_policy": kw.get("phase"),
                "repetitions": int(kw.get("repeat", "1")),
            })

        elif op == "MATERIAL":
            if len(pos) != 1:
                raise CRLError(f"{ctx}: MATERIAL requires material id")
            ir["materials"].append({
                "id": pos[0],
                "material_class": required(kw, "class", ctx),
                "role": required(kw, "role", ctx),
                "composition": kw.get("composition"),
                "conductivity_s_per_m": float(kw["conductivity"]) if "conductivity" in kw else None,
                "relative_permittivity": float(kw["permittivity"]) if "permittivity" in kw else None,
                "relative_permeability": float(kw["permeability"]) if "permeability" in kw else None,
                "optical_properties": None,
                "chemical_hazards": [],
            })

        elif op == "ENERGY":
            if len(pos) != 1:
                raise CRLError(f"{ctx}: ENERGY requires source id")
            profile = {}
            for key, value in kw.items():
                if key not in {"kind", "role", "measured", "source", "notes"}:
                    profile[key] = atom(value)
            ir["energy_inputs"].append({
                "id": pos[0],
                "kind": required(kw, "kind", ctx),
                "role": required(kw, "role", ctx),
                "profile": profile,
                "measured": bool(atom(kw.get("measured", "true"))),
                "source_ref": kw.get("source"),
                "notes": kw.get("notes", ""),
            })

        elif op == "PROCESS":
            if len(pos) != 1:
                raise CRLError(f"{ctx}: PROCESS requires process id")
            targets = required(kw, "targets", ctx).split(",")
            params = {}
            for key, value in kw.items():
                if key not in {"kind", "targets", "energy", "order", "historical", "simulation_only", "notes"}:
                    params[key] = atom(value)
            ir["processes"].append({
                "id": pos[0],
                "kind": required(kw, "kind", ctx),
                "targets": targets,
                "parameters": params,
                "energy_ref": kw.get("energy"),
                "order_index": int(kw["order"]) if "order" in kw else None,
                "historical_label": kw.get("historical"),
                "simulation_only": bool(atom(kw.get("simulation_only", "true"))),
                "notes": kw.get("notes", ""),
            })

        elif op == "ORIENT":
            if len(pos) != 1:
                raise CRLError(f"{ctx}: ORIENT requires reference frame")
            ir["orientation"]["reference"] = pos[0]
            ir["orientation"]["azimuth_deg"] = float(kw["azimuth"]) if "azimuth" in kw else None
            ir["orientation"]["inclination_deg"] = float(kw["inclination"]) if "inclination" in kw else None

        elif op == "ASTRO":
            ir["orientation"]["astronomical_context"] = dict(kw)

        elif op == "TIME_CONSTRAINT":
            if not pos:
                raise CRLError(f"{ctx}: TIME_CONSTRAINT requires text")
            ir["timing"]["historical_time_constraints"].append(" ".join(pos))

        elif op == "STEP":
            if not pos:
                raise CRLError(f"{ctx}: STEP requires text")
            ir["timing"]["sequence"].append(" ".join(pos))

        elif op == "ENV":
            allowed = {"temperature_c", "pressure_pa", "relative_humidity"}
            for key, value in kw.items():
                if key not in allowed:
                    raise CRLError(f"{ctx}: unsupported ENV field {key!r}")
                ir["environment"][key] = float(value)

        elif op == "ACTION":
            if not pos:
                raise CRLError(f"{ctx}: ACTION requires text")
            ir["human_actions"].append({
                "action": " ".join(pos),
                "trajectory_ref": kw.get("trajectory"),
                "body_state_measured": bool(atom(kw.get("body_state", "false"))),
                "notes": kw.get("notes", ""),
            })

        elif op == "MEASURE":
            if len(pos) != 1:
                raise CRLError(f"{ctx}: MEASURE requires channel")
            ir["measurements"].append({
                "channel": pos[0],
                "instrument": required(kw, "instrument", ctx),
                "sample_rate_hz": float(required(kw, "rate", ctx)),
                "calibration_ref": kw.get("calibration"),
                "uncertainty_model": kw.get("uncertainty"),
            })

        elif op == "CONTROL":
            if not pos:
                raise CRLError(f"{ctx}: CONTROL requires text")
            ir["controls"]["ablations"].append(" ".join(pos))

        elif op == "BLINDING":
            if len(pos) != 1:
                raise CRLError(f"{ctx}: BLINDING requires mode")
            ir["controls"]["blinding"] = pos[0]

        elif op == "RANDOMIZE":
            if len(pos) != 1:
                raise CRLError(f"{ctx}: RANDOMIZE requires true/false")
            ir["controls"]["randomization"] = bool(atom(pos[0]))

        elif op == "PREREGISTER":
            if len(pos) != 1:
                raise CRLError(f"{ctx}: PREREGISTER requires true/false")
            ir["controls"]["preregistered"] = bool(atom(pos[0]))

        elif op == "HOLDOUT":
            if len(pos) != 1:
                raise CRLError(f"{ctx}: HOLDOUT requires fraction")
            ir["controls"]["holdout_fraction"] = float(pos[0])

        elif op == "MODEL":
            if len(pos) != 1:
                raise CRLError(f"{ctx}: MODEL requires model name")
            ir["simulation"]["known_physics_models"].append(pos[0])

        elif op == "UNKNOWN":
            if not pos:
                raise CRLError(f"{ctx}: UNKNOWN requires id and optional description")
            uid = pos[0]
            description = " ".join(pos[1:]) if len(pos) > 1 else kw.get("description", "")
            ir["unknown_channels"].append({
                "id": uid,
                "description": description,
                "measurement_policy": kw.get("policy", "residual_only"),
                "notes": kw.get("notes", ""),
            })

        else:
            raise CRLError(f"{ctx}: unknown directive")

    if not seen_header:
        raise CRLError(f"{source_name}: missing RITUAL 0.1 header")
    if not seen_end:
        raise CRLError(f"{source_name}: missing END")
    for field in ("experiment_id", "title"):
        if not ir[field]:
            raise CRLError(f"{source_name}: missing required {field.upper()} directive")
    if not ir["source"]["tradition"]:
        raise CRLError(f"{source_name}: missing TRADITION")
    if not ir["source"]["witnesses"]:
        raise CRLError(f"{source_name}: at least one WITNESS is required")
    if not ir["claim"]["historical_description"]:
        raise CRLError(f"{source_name}: CLAIM is required")
    if not ir["geometry"]["primitives"]:
        raise CRLError(f"{source_name}: at least one geometry primitive is required")
    if not ir["measurements"]:
        raise CRLError(f"{source_name}: at least one MEASURE is required")
    if not ir["simulation"]["known_physics_models"]:
        raise CRLError(f"{source_name}: at least one MODEL is required")
    if not (0.0 <= ir["controls"]["holdout_fraction"] <= 1.0):
        raise CRLError(f"{source_name}: HOLDOUT must be in [0,1]")
    return ir


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("input", type=Path)
    p.add_argument("-o", "--output", type=Path)
    args = p.parse_args()

    ir = parse(args.input.read_text(encoding="utf-8"), str(args.input))
    rendered = json.dumps(ir, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
