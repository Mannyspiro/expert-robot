"""Frozen synthetic branches, scored through Merlin's actual review interface."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
from PIL import Image, ImageDraw

parser = argparse.ArgumentParser()
parser.add_argument("arm",type=Path)
parser.add_argument("--flags", default="{}", help="Operator-specified optional kwargs for the evaluated mode")
args = parser.parse_args()
here = Path(__file__).resolve().parent
base = here.parent / "baseline"
sys.path.insert(0,str(base/"python"))
import merlin
merlin.__path__.insert(0,str(args.arm.resolve()/"python/merlin"))
from merlin import drafting_control as dc
from merlin.wiring_sheet import read_sheet, wire_svg

raw = (here/"holdout.json").read_bytes()
digest = lambda data: hashlib.sha256(data).hexdigest()
assert digest(raw) == "bb987660af2d3f28a041eb56c7abb1a9c14003553c4df3aabb5ed30d4f88eb4b"
protocol = json.loads(raw)
kwargs=json.loads(args.flags)
rows=[]
started=time.perf_counter()

def score(root, spec, cases, partition):
    root.mkdir()
    source = root/"sheet.json"
    source.write_bytes(spec)
    title, _, parts, pins, nets = read_sheet(spec)
    svg = wire_svg(title,parts,pins,nets)
    (root/"wiring.svg").write_bytes(svg)
    for name, data in dc.guide_files(spec,svg,nets).items():
        (root/name).write_bytes(data)
    controls=json.loads((root/"draft-controls.json").read_bytes())
    for case in cases:
        case_id=case["id"]
        with Image.open(root/"conditioning-guide.png") as base_img:
            img=base_img.convert("RGB")
        img.putpixel((1,1),(132,141,151))
        if case_id in ("H2","H3"):
            branch = controls["nets"]["FAN"][1]["vertices_px"]
            x = round(0.39*branch[-2][0]+0.61*branch[-1][0])
            y1=round(branch[-1][1])
            y2=round(controls["nets"]["BYPASS"][0]["vertices_px"][0][1])
            draw=ImageDraw.Draw(img)
            draw.line([(x,y1),(x,y2)],fill=(31,31,31),width=3)
            if case_id=="H3":
                y=round(y1+0.75*(y2-y1))
                draw.rectangle((x-1,y-3,x+1,y+3),fill=(255,255,255))
        if case_id=="H4":
            luts=[max(0,min(255,round(.95*i+offset))) for offset in (6,5,3) for i in range(256)]
            img=img.point(luts)
        image_file=root/(case_id+".png")
        img.save(image_file,format="PNG")
        image_hash=digest(image_file.read_bytes())
        verdict=dict(schema="merlin-drafting-verdict/1",reviewer="isolated evaluator",
                     notes="Synthetic controlled judgement. Deliberately all pass for all registered images.",
                     source_sha256=controls["source_sha256"],guide_sha256=controls["guide_sha256"],
                     image_sha256=image_hash,checks=dict.fromkeys(dc.CHECKS,"pass"),nets=[
                         {"id":name,"status":"pass","connections":[
                             {"from":route["from"],"to":route["to"],"status":"pass"} for route in routes]}
                         for name,routes in controls["nets"].items()])
        vf=root/(case_id+"-observation.json"); vf.write_text(json.dumps(verdict))
        out=root/(case_id+"-review")
        start=time.perf_counter()
        err=None
        diagnostics={}
        try:
            record=dc.review_wiring(source,root,image_file,vf,out,**kwargs)
            decision=record["decision"]
            diagnostics={k:v for k,v in record.items() if k not in {
                "schema","decision","reviewer","source_sha256","guide_sha256","image_sha256",
                "verdict_sha256","size_px","aspect_ratio_matches","checks","nets","notes","authority"}}
        except ValueError as exc:
            err=str(exc); decision="validation_refused"
        elapsed=time.perf_counter()-start
        label=("accept" if decision=="accepted" else "withhold"
               if decision in ("validation_refused","rejected","abstain","requires_review","unknown") else "unscored")
        rows.append(dict(id=case_id,partition=partition,expected_label=case["expected"],actual_label=label,
                         passed=label==case["expected"],decision=decision,diagnostics=diagnostics,
                         error=err,review_file_emitted=(out/"review.json").exists(),source_sha256=digest(spec),
                         image_sha256=image_hash,review_seconds=round(elapsed,4)))

with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    score(root/"development",(base/"examples/merlin/lab-signal-sheet.json").read_bytes(),protocol["development"],"development")
    score(root/"heldout",json.dumps(protocol["sheet"],indent=2).encode(),protocol["heldout"],"heldout")
print(json.dumps(dict(arm=args.arm.name,source_sha256=digest(Path(dc.__file__).read_bytes()),
                      protocol_sha256=digest(raw),flags=kwargs,wall_seconds=round(time.perf_counter()-started,4),
                      passed_development=sum(x["passed"] for x in rows if x["partition"]=="development"),
                      passed_heldout=sum(x["passed"] for x in rows if x["partition"]=="heldout"),
                      accepted=sum(x["decision"]=="accepted" for x in rows),
                      results=rows),indent=2))
