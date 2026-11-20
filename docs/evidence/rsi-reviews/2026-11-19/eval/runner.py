"""Execute frozen synthetic drafting controls against one local arm, without networking."""
import argparse
import copy
import hashlib
import io
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw

here = Path(__file__).resolve().parent
args = argparse.ArgumentParser()
args.add_argument("arm", type=Path)
args = args.parse_args()
baseline = here.parent / "baseline"
sys.path.insert(0, str(baseline / "python"))
import merlin
merlin.__path__.insert(0, str(args.arm.resolve()/"python/merlin"))
from merlin import drafting_control as dc
from merlin.wiring_sheet import read_sheet, wire_svg

sha = lambda b: hashlib.sha256(b).hexdigest()
hold = (here/"holdout.json").read_bytes()
assert sha(hold) == "fa4f65757e4be864b067d9aa68fdbb48e965314c5ec8fffec011021607dcdb91"
assert sha((here/"amendment.json").read_bytes()) == "b10f9f63cab6dbd46d64ad96151b3b89bf23ba46827d84fa4535b027c1bfa866"
data = json.loads(hold)
start = time.perf_counter()
rows = []
def exercise(parent, name, raw):
    parent.mkdir()
    source = parent/"sheet.json"
    source.write_bytes(raw)
    title,_,parts,pins,nets = read_sheet(raw)
    svg = wire_svg(title,parts,pins,nets)
    (parent/"wiring.svg").write_bytes(svg)
    for f,content in dc.guide_files(raw,svg,nets).items():
        (parent/f).write_bytes(content)
    controls = json.loads((parent/"draft-controls.json").read_bytes())
    for cid in (["D0"] if name=="development" else [item[0] for item in data["cases"]]):
        with Image.open(parent/"conditioning-guide.png") as original:
            img = original.convert("RGB")
        img.putpixel((1,1),(131,141,159))
        if cid in ("B2","B3"):
            line = controls["nets"]["SIGNAL"][1]["vertices_px"]
            # A vertical, visibly conductive addition between two previously disjoint nets.
            x = (line[-2][0]+line[-1][0])/2
            end_y = controls["nets"]["REF"][0]["vertices_px"][0][1]
            ImageDraw.Draw(img).line([(x,line[-1][1]),(x,end_y)],fill="black",width=4)
        if cid=="B5":
            img = img.crop((0,0,img.width-1,img.height))
        candidate = parent/(cid+".png")
        img.save(candidate,format="BMP" if cid=="B4" else "PNG")
        pix = candidate.read_bytes()
        v = dict(schema="merlin-drafting-verdict/1",reviewer="independent synthetic evaluator",
                 notes="Controlled synthetic independent schematic.",
                 source_sha256=controls["source_sha256"],guide_sha256=controls["guide_sha256"],
                 image_sha256=sha(pix),checks=dict.fromkeys(dc.CHECKS,"pass"),nets=[
                 {"id":net,"status":"pass","connections":[{"from":r["from"],"to":r["to"],"status":"pass"} for r in cons]}
                 for net,cons in controls["nets"].items()])
        if cid=="B1":
            by_net={row["id"]:row["connections"] for row in v["nets"]}
            a,b = by_net["SIGNAL"][0],by_net["REF"][0]
            a["to"],b["to"]=b["to"],a["to"]
        if cid=="B2": v["checks"]["no_extra_connections"]="fail"
        verdict = parent/(cid+"-verdict.json"); verdict.write_text(json.dumps(v))
        opened,loads=[],[]
        original_open=Image.open
        def observed_open(fp,*pargs,**kwargs):
            match = isinstance(fp,io.BytesIO) and fp.getvalue()==pix
            if match:
                fmts=kwargs.get("formats",pargs[1] if len(pargs)>1 else None)
                opened.append(None if fmts is None else list(fmts))
            asset=original_open(fp,*pargs,**kwargs)
            if match:
                load=asset.load
                def loading(*a,**k):
                    loads.append(asset.format)
                    return load(*a,**k)
                asset.load=loading
            return asset
        before = time.perf_counter()
        error=None
        with patch.object(Image,"open",observed_open):
            try: decision=dc.review_wiring(source,parent,candidate,verdict,parent/(cid+"-review"))["decision"]
            except (ValueError,OSError) as exc: decision="rejected"; error=f"{type(exc).__name__}: {exc}"
        label=decision
        expected = "accepted" if cid in ("D0","B0") else "rejected"
        if cid=="B4":
            expected = "rejected_without_general_dispatch"
            if decision=="rejected" and all(v == ["PNG"] for v in opened): label=expected
        if cid=="B5":
            expected = "rejected_before_load"
            if decision=="rejected" and not loads: label=expected
        rows.append(dict(id=cid,partition=name,expected_label=expected,actual_label=label,
                         decision=decision,passed=label==expected,source_sha256=sha(raw),candidate_sha256=sha(pix),
                         candidate_only_open_calls=len(opened),candidate_only_load_calls=len(loads),
                         allowed_formats_at_open=opened,error=error,seconds=round(time.perf_counter()-before,4)))

with tempfile.TemporaryDirectory() as temp:
    root=Path(temp)
    exercise(root/"dev","development",(baseline/"examples/merlin/lab-signal-sheet.json").read_bytes())
    exercise(root/"hold","heldout",json.dumps(data["sheet"],indent=2).encode())
print(json.dumps(dict(arm=args.arm.name,source_sha256=sha(Path(dc.__file__).read_bytes()),protocol_sha256=sha(hold),
                      elapsed_seconds=round(time.perf_counter()-start,3),results=rows),indent=2))
