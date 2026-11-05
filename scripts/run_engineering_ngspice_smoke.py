#!/usr/bin/env python3
"""Reproducible Engineering IR -> SPICE -> ngspice qualification smoke."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from merlin.engineering_ir import (
    EngineeringProject, Net, Part, Pin, export_netlist,
    export_openscad, export_spice_netlist,
)
from merlin.freecad_bridge import write_freecad_bundle
from merlin.ngspice_engine import run_ngspice


def main() -> int:
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/engineering-ngspice")
    output.mkdir(parents=True, exist_ok=True)
    project = EngineeringProject(
        "merlin-resistor-divider", "mm",
        parts=(
            Part("V1", "5V supply", (Pin("1", "positive"), Pin("2", "ground"))),
            Part("R1", "1 kohm load", (Pin("1", "input"), Pin("2", "return"))),
        ),
        nets=(
            Net("SUPPLY", ("V1.1", "R1.1"), nominal_voltage_v=5.0),
            Net("GND", ("V1.2", "R1.2"), nominal_voltage_v=0.0),
        ),
    )
    spice = export_spice_netlist(
        project,
        {"V1": {"kind": "V", "value": "5"},
         "R1": {"kind": "R", "value": "1k"}},
        ground_net="GND",
    )
    (output / "engineering-ir.json").write_text(
        json.dumps(export_netlist(project), sort_keys=True, indent=2) + "\\n",
        encoding="utf-8",
    )
    (output / "assembly.scad").write_text(export_openscad(project), encoding="utf-8")
    (output / "divider.cir").write_text(spice, encoding="utf-8")
    cad = write_freecad_bundle(project, output)
    result = run_ngspice(spice, timeout_seconds=30, max_memory_bytes=512 * 1024 * 1024)
    result_path = output / "ngspice-result.json"
    result_path.write_bytes(result["artifact_bytes"])
    manifest = {
        "schema": "merlin-engineering-integration/1",
        "project": project.name,
        "spice_netlist_sha256": hashlib.sha256(spice.encode("utf-8")).hexdigest(),
        "ngspice_result_sha256": hashlib.sha256(result["artifact_bytes"]).hexdigest(),
        "ngspice_returncode": result["metadata"]["returncode"],
        "ngspice_wall_seconds": result["metadata"]["wall_seconds"],
        "freecad_macro": str(Path(cad["macro"]).name),
        "freecad_runtime": "macro-generated; runtime execution not attempted in this smoke",
        "authority": "qualification-only",
        "promotion_authority": False,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\\n", encoding="utf-8"
    )
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
