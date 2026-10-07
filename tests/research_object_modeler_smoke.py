#!/usr/bin/env python3
import importlib.util, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts"/"generate_research_object_candidates.py"
EXAMPLE=ROOT/"config"/"examples"/"research_object_demo.json"

spec=importlib.util.spec_from_file_location("modeler",SCRIPT)
module=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

payload=json.loads(EXAMPLE.read_text(encoding="utf-8"))
result=module.generate(payload)
assert result["candidate_count"]>=3
assert result["evidence_ceiling"]=="pre_fea_topology_generation"
assert result["ranked_survivors"]
assert all(x["connected"] for x in result["ranked_survivors"])
assert all(x["obstacle_violation_count"]==0 for x in result["ranked_survivors"])

print("research object modeler: PASS")
