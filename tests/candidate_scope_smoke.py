#!/usr/bin/env python3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
validator=ROOT/"scripts"/"validate_candidate_scope.py"
policy=ROOT/"config"/"auto_promotion_scope.json"

def run(*args,check=True):
    return subprocess.run(args,check=check,text=True,capture_output=True)

with tempfile.TemporaryDirectory() as td:
    r=Path(td)
    run("git","init",str(r))
    run("git","-C",str(r),"config","user.email","test@example.invalid")
    run("git","-C",str(r),"config","user.name","scope-test")
    p=r/"cpp/src/proof_search.cpp"
    p.parent.mkdir(parents=True)
    p.write_text("int capability = 1;\n")
    run("git","-C",str(r),"add",".")
    run("git","-C",str(r),"commit","-m","base")
    base=run("git","-C",str(r),"rev-parse","HEAD").stdout.strip()

    p.write_text("int capability = 2;\n")
    run("git","-C",str(r),"add",".")
    run("git","-C",str(r),"commit","-m","allowed")
    allowed=run("git","-C",str(r),"rev-parse","HEAD").stdout.strip()
    good=run(sys.executable,str(validator),str(r),"--base-sha",base,"--candidate-sha",allowed,"--policy",str(policy))
    assert '"scope_allowed": true' in good.stdout.lower()

    wf=r/".github/workflows/escape.yml"
    wf.parent.mkdir(parents=True)
    wf.write_text("name: forbidden\n")
    run("git","-C",str(r),"add",".")
    run("git","-C",str(r),"commit","-m","forbidden")
    bad=run(sys.executable,str(validator),str(r),"--base-sha",base,"--candidate-sha","HEAD","--policy",str(policy),check=False)
    assert bad.returncode != 0
    assert "forbidden" in bad.stdout.lower()

print("candidate scope smoke: PASS")
