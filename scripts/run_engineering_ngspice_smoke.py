#!/usr/bin/env python3
"""Reproducible Engineering IR -> FreeCAD -> SPICE -> ngspice integration smoke."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from merlin.engineering_ir import (
    EngineeringProject, Net, Part, Pin, export_netlist,
    export_openscad, export_spice_netlist,
)
from merlin.freecad_bridge import write_freecad_bundle
from merlin.freecad_document_bridge import (
    build_document_export_macro, register_freecad_document_artifact,
)
from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.ngspice_engine import run_ngspice
from merlin.project_registry import MerlinRegistry


def find_freecad_command() -> str:
    explicit = os.environ.get("FREECAD_CMD")
    if explicit and Path(explicit).is_file():
        return explicit
    for name in ("FreeCADCmd", "freecadcmd"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in (
        "/usr/lib/freecad/bin/FreeCADCmd",
        "/usr/lib/freecad/bin/freecadcmd",
        "/usr/bin/FreeCADCmd",
        "/usr/bin/freecadcmd",
    ):
        if Path(candidate).is_file():
            return candidate
    raise RuntimeError("FreeCADCmd/freecadcmd is required for actual headless CAD qualification")


def run_freecad_macro(command: str, macro_path: Path, cwd: Path) -> str:
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    absolute_macro = macro_path.expanduser().resolve()
    completed = subprocess.run(
        [command, str(absolute_macro)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
        env=env,
    )
    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    if completed.returncode != 0:
        raise RuntimeError("FreeCAD macro failed: " + output[-5000:])
    return output[-12000:]


def main() -> int:
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/engineering-ngspice")
    output.mkdir(parents=True, exist_ok=True)
    project = EngineeringProject(
        "merlin-resistor-divider", "mm",
        parts=(
            Part("V1", "5V supply", (Pin("1", "positive"), Pin("2", "ground"))),
            Part("R1", "upper 1 kohm resistor", (Pin("1", "input"), Pin("2", "output"))),
            Part("R2", "lower 1 kohm resistor", (Pin("1", "input"), Pin("2", "return"))),
        ),
        nets=(
            Net("SUPPLY", ("V1.1", "R1.1"), nominal_voltage_v=5.0),
            Net("MID", ("R1.2", "R2.1"), nominal_voltage_v=2.5),
            Net("GND", ("V1.2", "R2.2"), nominal_voltage_v=0.0),
        ),
    )
    spice = export_spice_netlist(
        project,
        {"V1": {"kind": "V", "value": "5"},
         "R1": {"kind": "R", "value": "1k"},
         "R2": {"kind": "R", "value": "1k"}},
        ground_net="GND",
        measure_nets=("MID",),
    )
    (output / "engineering-ir.json").write_text(
        json.dumps(export_netlist(project), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "assembly.scad").write_text(export_openscad(project), encoding="utf-8")
    (output / "divider.cir").write_text(spice, encoding="utf-8")

    # Run the electrical simulation first so its result survives a later CAD
    # runtime failure and remains independently inspectable in the Actions artifact.
    (output / "ngspice-measurement.json").write_text(
        json.dumps({
            "node": "MID",
            "expected_voltage_v": 2.5,
            "measured_voltage_v": measured_mid_voltage,
            "status": "PASS",
            "netlist_sha256": hashlib.sha256(spice.encode("utf-8")).hexdigest(),
            "result_sha256": hashlib.sha256(result["artifact_bytes"]).hexdigest(),
        }, sort_keys=True, indent=2) + "\\n",
        encoding="utf-8",
    )

    cad = write_freecad_bundle(project, output)
    freecad_cmd = find_freecad_command()
    import_macro_log = run_freecad_macro(freecad_cmd, Path(cad["macro"]), output)
    fcstd_path = Path(cad["fcstd_output"])
    step_path = Path(cad["step_output"])
    if not fcstd_path.is_file() or fcstd_path.stat().st_size == 0:
        raise RuntimeError("FreeCAD did not create the native FCStd document")
    if not step_path.is_file() or step_path.stat().st_size == 0:
        raise RuntimeError("FreeCAD did not export the STEP assembly")

    mesh_path = output / "freecad-mesh.json"
    mesh_macro_path = output / "freecad_document_export.FCMacro"
    mesh_macro_path.write_text(
        build_document_export_macro(step_path, mesh_path),
        encoding="utf-8",
    )
    mesh_macro_log = run_freecad_macro(freecad_cmd, mesh_macro_path, output)
    if not mesh_path.is_file() or mesh_path.stat().st_size == 0:
        raise RuntimeError("FreeCAD STEP import did not produce an assembly mesh")
    registry = MerlinRegistry(output / "canonical-registry")
    registry.register_project(
        "merlin-engineering-smoke", "Merlin Engineering Smoke",
        metadata={"authority": "qualification-only", "promotion_authority": False},
    )
    graph = MerlinKnowledgeGraph(output / "canonical-graph.sqlite3")
    registration = register_freecad_document_artifact(
        registry=registry,
        graph=graph,
        project_id="merlin-engineering-smoke",
        logical_path="cad/freecad-import-smoke.json",
        content=mesh_path.read_bytes(),
    )
    if not registration["artifact_verified"]:
        raise RuntimeError("FreeCAD mesh did not verify in the canonical artifact registry")
    (output / "freecad-registration.json").write_text(
        json.dumps(registration, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    result = run_ngspice(spice, timeout_seconds=30, max_memory_bytes=512 * 1024 * 1024)
    result_payload = json.loads(result["artifact_bytes"].decode("utf-8"))
    measurement = re.search(
        r"(?im)^\s*v_mid\s*=\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)\s*$",
        result_payload.get("log", ""),
    )
    if measurement is None:
        raise RuntimeError("ngspice did not emit the expected v_mid operating-point measurement")
    measured_mid_voltage = float(measurement.group(1))
    if not math.isclose(measured_mid_voltage, 2.5, rel_tol=0.0, abs_tol=1e-6):
        raise RuntimeError(
            f"resistor-divider operating point mismatch: expected 2.5 V, got {measured_mid_voltage}"
        )
    result_path = output / "ngspice-result.json"
    result_path.write_bytes(result["artifact_bytes"])
    manifest = {
        "schema": "merlin-engineering-integration/2",
        "project": project.name,
        "spice_netlist_sha256": hashlib.sha256(spice.encode("utf-8")).hexdigest(),
        "ngspice_result_sha256": hashlib.sha256(result["artifact_bytes"]).hexdigest(),
        "ngspice_returncode": result["metadata"]["returncode"],
        "ngspice_wall_seconds": result["metadata"]["wall_seconds"],
        "ngspice_expected_mid_voltage_v": 2.5,
        "ngspice_measured_mid_voltage_v": measured_mid_voltage,
        "ngspice_measurement_status": "PASS",
        "freecad_command": freecad_cmd,
        "freecad_runtime": "executed",
        "freecad_fcstd_sha256": hashlib.sha256(fcstd_path.read_bytes()).hexdigest(),
        "freecad_step_sha256": hashlib.sha256(step_path.read_bytes()).hexdigest(),
        "freecad_mesh_sha256": hashlib.sha256(mesh_path.read_bytes()).hexdigest(),
        "freecad_registration": registration,
        "freecad_import_log_tail": import_macro_log[-2000:],
        "freecad_mesh_log_tail": mesh_macro_log[-2000:],
        "authority": "qualification-only",
        "promotion_authority": False,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
