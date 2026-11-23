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
    "run_records":[
        {"run_id":"eval-1","kind":"evaluation","promoted_lineage":False,"candidate_sha":csha,"base_sha":bsha,"collared_execution":True,"collar_tripped":False},
        {"run_id":"eval-2","kind":"evaluation","promoted_lineage":False,"candidate_sha":csha,"base_sha":bsha,"collared_execution":True,"collar_tripped":False},
        {"run_id":"eval-3","kind":"evaluation","promoted_lineage":False,"candidate_sha":csha,"base_sha":bsha,"collared_execution":True,"collar_tripped":False},
    ],
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
    ok=subprocess.run([sys.executable,str(validator),str(p),"--candidate-sha",csha,"--base-sha",bsha,"--source-run-id","123"],text=True,capture_output=True,check=True)
    assert '"collared_execution": true' in ok.stdout.lower()

    # Valid evidence from a different trusted run cannot be replayed here.
    for wrong_id in (124, True, "123"):
        p.write_text(json.dumps(dict(passing, source_run_id=wrong_id)))
        replay=subprocess.run([sys.executable,str(validator),str(p),"--candidate-sha",csha,"--base-sha",bsha,"--source-run-id","123"],text=True,capture_output=True)
        assert replay.returncode != 0
        assert "source_run_id_matches" in json.loads(replay.stdout)["failed_checks"]

    p.write_text(json.dumps(dict(passing, candidate_sha="c"*40)))
    wrong_sha=subprocess.run([sys.executable,str(validator),str(p),"--candidate-sha",csha,"--base-sha",bsha,"--source-run-id","123"],text=True,capture_output=True)
    assert wrong_sha.returncode != 0
    assert "candidate_sha_matches" in json.loads(wrong_sha.stdout)["failed_checks"]

    promoted=dict(passing)
    promoted["run_records"]=[dict(x) for x in passing["run_records"]]
    promoted["run_records"][1]["kind"]="lineage"
    promoted["run_records"][1]["promoted_lineage"]=True
    p.write_text(json.dumps(promoted))
    lineage=subprocess.run([sys.executable,str(validator),str(p),"--candidate-sha",csha,"--base-sha",bsha,"--source-run-id","123"],text=True,capture_output=True)
    assert lineage.returncode != 0
    assert "all_runs_are_real_evaluations" in lineage.stdout
    assert "no_promoted_lineage_counted_as_run" in lineage.stdout

    passing["runtime_result"]["tripped"]=True
    p.write_text(json.dumps(passing))
    bad=subprocess.run([sys.executable,str(validator),str(p),"--candidate-sha",csha,"--base-sha",bsha,"--source-run-id","123"],text=True,capture_output=True)
    assert bad.returncode != 0
    assert "collar_not_tripped" in bad.stdout

print("collar evidence validation smoke: PASS")
