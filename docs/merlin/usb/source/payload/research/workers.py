"""Build and qualify small, reusable research tools from reviewed templates."""
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

TOOLS={
    "chip-routing":("chip", "Ranked floorplan and routing metrics"),
    "thermal-physics":("physics", "Compare solver timings and exactness"),
    "metamaterial-printing":("matter", "Material inventory and independent scan evidence"),
}
SOURCES={
    "chip-routing":("Python", "https://github.com/python/cpython"),
    "thermal-physics":("NumPy", "https://github.com/numpy/numpy"),
    "metamaterial-printing":("OpenSCAD", "https://github.com/openscad/openscad"),
}
TEMPLATE='''"""Merlin research tool. Generated from a reviewed template."""
from argparse import ArgumentParser
from pathlib import Path
import json

def analyze(report):
    data = report[SECTION]
    return {name: data[name] for name in FIELDS}

if __name__ == "__main__":
    cli=ArgumentParser(description=DESCRIPTION)
    cli.add_argument("receipt", type=Path)
    args=cli.parse_args()
    print(json.dumps(analyze(json.loads(args.receipt.read_text())),indent=2,allow_nan=False))
'''
FIELDS={
    "chip":("candidate","baseline","ranked_designs","held_out"),
    "physics":("status","active_backend","cases"),
    "matter":("winner","held_out","copies_exact","negative_controls"),
}


def create(state,specialty,name,report):
    if specialty not in TOOLS or not re.fullmatch(r"[a-z][a-z0-9-]{2,58}",name):
        raise ValueError("Choose a supported specialty and a lowercase tool name")
    section,description=TOOLS[specialty]
    project,url=SOURCES[specialty]
    text=TEMPLATE.replace("SECTION",repr(section)).replace("FIELDS",repr(FIELDS[section])).replace("DESCRIPTION",repr(description))
    root=state/"xenomaths"/"workers"
    root.mkdir(parents=True,exist_ok=True)
    fingerprint=sha256(text.encode()).hexdigest()
    dest=root/name
    if dest.exists():
        receipt=json.loads((dest/"Tool_Receipt.json").read_text())
        if receipt["sha256"]!=fingerprint:
            raise ValueError("Worker name already has a different tool")
        return receipt
    expected={key:report[section][key] for key in FIELDS[section]}
    with TemporaryDirectory(dir=root,prefix=".candidate-") as temporary:
        temp=Path(temporary)
        candidate=temp/"release"
        candidate.mkdir()
        tool=candidate/"tool.py"
        tool.write_text(text)
        data=temp/"input.json"
        data.write_text(json.dumps(report))
        probe=subprocess.run([sys.executable,"-I","-B",str(tool),str(data)],cwd=temp,
                             capture_output=True,text=True,timeout=8,check=True)
        if json.loads(probe.stdout)!=json.loads(json.dumps(expected)):
            raise RuntimeError("The generated tool did not match its reference data")
        data.write_text("{}")
        rejected=subprocess.run([sys.executable,"-I","-B",str(tool),str(data)],cwd=temp,
                              capture_output=True,timeout=8).returncode!=0
        if not rejected:raise RuntimeError("Missing-input control failed")
        receipt={"name":name,"specialty":specialty,"source":{"name":project,"url":url},
                 "sha256":fingerprint,"validation":{"reference":True,"missing_input_rejected":True},
                 "scope":"Tool analyzes existing simulation evidence. Workers use local templates."}
        (candidate/"Tool_Receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
        try:
            candidate.rename(dest)
        except OSError:
            if not dest.is_dir():raise
            existing=json.loads((dest/"Tool_Receipt.json").read_text())
            if existing["sha256"]!=fingerprint:raise ValueError("Worker name already has a different tool")
    return receipt


def list_tools(state):
    root=state/"xenomaths"/"workers"
    return [json.loads(p.read_text()) for p in sorted(root.glob("*/Tool_Receipt.json"))]
