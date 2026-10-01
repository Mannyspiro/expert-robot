#!/usr/bin/env python3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
validator=ROOT/"scripts/validate_blind_candidate.py"
policy=ROOT/"config/blind_evaluation_policy.json"

def run(*args,check=True):
    return subprocess.run(args,check=check,text=True,capture_output=True)

with tempfile.TemporaryDirectory() as td:
    repo=Path(td)
    run("git","init",str(repo))
    run("git","-C",str(repo),"config","user.email","test@example.invalid")
    run("git","-C",str(repo),"config","user.name","blind-test")
    p=repo/"cpp/src/proof_search.cpp"
    p.parent.mkdir(parents=True)
    p.write_text("int generic_strategy = 1;\n")
    run("git","-C",str(repo),"add",".")
    run("git","-C",str(repo),"commit","-m","base")
    base=run("git","-C",str(repo),"rev-parse","HEAD").stdout.strip()

    p.write_text("int generic_strategy = 2;\n")
    run("git","-C",str(repo),"add",".")
    run("git","-C",str(repo),"commit","-m","clean")
    clean=run("git","-C",str(repo),"rev-parse","HEAD").stdout.strip()
    run(sys.executable,str(validator),str(repo),"--base-sha",base,"--candidate-sha",clean,"--policy",str(policy))

    p.write_text('const char* leaked = "holdout-geometry-distance-symm";\n')
    run("git","-C",str(repo),"add",".")
    run("git","-C",str(repo),"commit","-m","leak")
    leak=run("git","-C",str(repo),"rev-parse","HEAD").stdout.strip()
    bad=run(sys.executable,str(validator),str(repo),"--base-sha",base,"--candidate-sha",leak,"--policy",str(policy),check=False)
    assert bad.returncode != 0
    assert "holdout-geometry-distance-symm" in bad.stdout

    p.write_text('const char* leaked = "hard2-holdout-003";\n')
    run("git","-C",str(repo),"add",".")
    run("git","-C",str(repo),"commit","-m","hard-v2-leak")
    hard_leak=run("git","-C",str(repo),"rev-parse","HEAD").stdout.strip()
    bad=run(sys.executable,str(validator),str(repo),"--base-sha",base,"--candidate-sha",hard_leak,"--policy",str(policy),check=False)
    assert bad.returncode != 0
    assert "hard2-holdout-003" in bad.stdout

print("blind candidate smoke: PASS")
