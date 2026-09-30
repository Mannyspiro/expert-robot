#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
policy=json.loads((ROOT/"config/blind_evaluation_policy.json").read_text())

with tempfile.TemporaryDirectory() as td:
    out=Path(td)/"view"
    subprocess.run([
        sys.executable,str(ROOT/"scripts/build_generation_view.py"),
        str(ROOT),str(out),"--policy",str(ROOT/"config/blind_evaluation_policy.json")
    ],check=True,capture_output=True,text=True)

    assert not (out/"config/benchmarks").exists()
    assert not (out/"tests").exists()
    assert not (out/".github").exists()
    assert (out/"GENERATION_VIEW_MANIFEST.json").exists()
    for item in out.rglob("*"):
        if not item.is_file():
            continue
        try:
            text=item.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for token in policy["hidden_identifiers"]:
            assert token not in text, (item,token)

print("blind generation view smoke: PASS")
