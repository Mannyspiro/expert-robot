#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
validator=ROOT/"scripts"/"validate_collar_evidence.py"
csha="a"*40
bsha="b"*40

passing={
    "schema_version":1,
    "candidate_id":"candidate-1",
    "candidate_sha":csha,
    "parent_sha":bsha,
    "source_run_id":123,
    "run_records":[],
    "generation_budget":{"estimated":True,"recommended_runs":5,"actual_runs":3},
    "lineage_verified":True,
    "core_integrity_verified":True,
    "authority_change":"same",
    "runtime_result":{
        "tripped":False,
        "promotion_authority":False,
        "image_digest_pinned":True,
        "plaintext_persisted":False,
        "generation_key_persisted":False,
    },
}
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/"evidence.json"
    p.write_text(json.dumps(passing))
    ok=subprocess.run([sys.executable,str(validator),str(p),"--candidate-sha",csha,"--base-sha",bsha],text=True,capture_output=True,check=True)
    assert '"collared_execution": true' in ok.stdout.lower()

    passing["runtime_result"]["tripped"]=True
    p.write_text(json.dumps(passing))
    bad=subprocess.run([sys.executable,str(validator),str(p),"--candidate-sha",csha,"--base-sha",bsha],text=True,capture_output=True)
    assert bad.returncode != 0
    assert "collar_not_tripped" in bad.stdout

print("collar evidence validation smoke: PASS")
