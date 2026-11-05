#!/usr/bin/env python3
"""Persist validated CAD/MCFC metadata and wiring relationships in the canonical registry."""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from canonical_registry import connect, initialize
from cad_mcfc_model import validate_matrix, validate_simulation, validate_wiring

def store_metadata(database,project_id,artifact_sha256,metadata):
    if len(artifact_sha256)!=64 or any(c not in "0123456789abcdef" for c in artifact_sha256):
        raise ValueError("artifact SHA-256 required")
    if "solver" in metadata:
        metadata=validate_simulation(metadata)
    else:
        required=("metadata_version","artifact_sha256","artifact_family","units","coordinate_frame","revision","provenance")
        if any(k not in metadata for k in required): raise ValueError("CAD metadata missing required fields")
        if metadata["metadata_version"]!="1.0" or metadata["artifact_sha256"]!=artifact_sha256:
            raise ValueError("CAD metadata version or artifact identity mismatch")
        if metadata["artifact_family"] not in ("cad_model","cad_drawing","cad_native_project","mesh_model","simulation_mesh","simulation_input","simulation_result","electrical_netlist","electrical_schematic","pcb_layout","manufacturing_data"):
            raise ValueError("unsupported engineering artifact family")
        if not isinstance(metadata["units"],dict) or not all(metadata["units"].get(k) for k in ("length","angle")):
            raise ValueError("units must declare length and angle")
        frame=metadata["coordinate_frame"]
        if not isinstance(frame,dict) or not all(frame.get(k) for k in ("frame_id","handedness","axis_convention")):
            raise ValueError("coordinate frame must declare frame_id, handedness and axis_convention")
        if frame["handedness"] not in ("right","left"): raise ValueError("unsupported coordinate handedness")
        provenance=metadata["provenance"]
        if not isinstance(provenance,dict) or not provenance.get("operation") or not provenance.get("source_artifact_sha256"):
            raise ValueError("engineering provenance must bind source artifact and operation")
    if "coordinate_frame" in metadata and "transform_to_parent" in metadata["coordinate_frame"]:
        validate_matrix([metadata["coordinate_frame"]["transform_to_parent"][i:i+4] for i in range(0,16,4)])
    payload=json.dumps(metadata,sort_keys=True,separators=(",",":"))
    with connect(database) as db:
        if not db.execute("""SELECT 1 FROM project_intakes pi JOIN artifacts a ON a.intake_id=pi.intake_id
          WHERE pi.project_id=? AND a.sha256=? LIMIT 1""",(project_id,artifact_sha256)).fetchone():
            raise ValueError("artifact must already be registered to this project")
        db.execute("INSERT OR REPLACE INTO engineering_metadata VALUES(?,?,?,?)",
          (artifact_sha256,project_id,payload,datetime.now(timezone.utc).isoformat()))
    return {"artifact_sha256":artifact_sha256,"status":"metadata_registered"}

def store_wiring(database,project_id,connections):
    normalized=validate_wiring(connections)
    with connect(database) as db:
        if not db.execute("SELECT 1 FROM projects WHERE project_id=?",(project_id,)).fetchone():
            raise ValueError("unknown project")
        for c in connections:
            db.execute("""INSERT OR REPLACE INTO wiring_connections
              VALUES(?,?,?,?,?,?,?,?)""",(project_id,c["connection_id"],c["from_node"],c["from_pin"],
              c["to_node"],c["to_pin"],c["net_name"],json.dumps(c,sort_keys=True)))
    return {"project_id":project_id,"connection_count":len(connections),"net_count":len(normalized["nets"])}

def main():
    p=argparse.ArgumentParser(); p.add_argument("project_id"); p.add_argument("input",type=Path)
    p.add_argument("--database",default="data/merlin.sqlite3"); p.add_argument("--artifact-sha256")
    a=p.parse_args(); initialize(a.database); data=json.loads(a.input.read_text())
    if data.get("kind")=="wiring": result=store_wiring(a.database,a.project_id,data["connections"])
    elif data.get("kind") in ("cad","simulation"):
        if not a.artifact_sha256: raise SystemExit("--artifact-sha256 is required for CAD/simulation metadata")
        result=store_metadata(a.database,a.project_id,a.artifact_sha256,data["metadata"])
    else: raise SystemExit("kind must be wiring, cad or simulation")
    print(json.dumps(result,indent=2))
if __name__=="__main__": main()
