"""Generate and validate a registered editing guide for a measured wiring sheet."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from PIL import Image
from .wiring_sheet import read_sheet, wire_svg


CANVAS = (1536, 1024)
MARKS = {"A": [64, 64], "B": [1472, 64], "C": [1472, 960], "D": [64, 960]}
CHECKS = ("component_labels", "geometry", "fiducials", "no_extra_connections")
STATES = ("pass", "fail", "unknown")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def limited(path, limit):
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"{path.name} exceeds its size limit")
    return data


def registered_sheet(svg, nets):
    # The sheet's own viewBox is in mm; the outer guide is in pixels.
    sheet = ET.fromstring(svg)
    _, _, w, h = map(float, sheet.attrib["viewBox"].split())
    width, height = CANVAS
    scale = min((width - 192) / w, (height - 224) / h)
    x0, y0 = (width - w * scale) / 2, (height - h * scale) / 2
    uri = "{http://www.w3.org/2000/svg}"
    ET.register_namespace("", uri[1:-1])
    outer = ET.Element(uri+"svg", width=str(width), height=str(height),
                       viewBox=f"0 0 {width} {height}")
    ET.SubElement(outer, uri+"rect", width=str(width), height=str(height), fill="#faf7ed")
    sheet.attrib.update(x=str(x0), y=str(y0), width=str(w * scale), height=str(h * scale))
    outer.append(sheet)
    for label, (x,y) in MARKS.items():
        ET.SubElement(outer, uri+"path", d=f"M {x-15} {y} h 30 M {x} {y-15} v 30",
                      stroke="#172a34", **{"stroke-width": "3"})
        ET.SubElement(outer, uri+"circle", cx=str(x), cy=str(y), r="7", fill="none", stroke="#172a34")
        ET.SubElement(outer, uri+"text", x=str(x+19), y=str(y+6), fill="#172a34",
                      **{"font-family":"sans-serif","font-size":"18"}).text = label
    pins, routes = {}, {}
    def pixels(x,y):
        return [round(x0 + scale*x, 4), round(y0 + scale*y, 4)]
    for group in sheet.findall(uri+"g"):
        if "data-pin" in group.attrib:
            pin = group.find(uri+"circle")
            pins[group.attrib["data-pin"]] = pixels(float(pin.attrib["cx"]),float(pin.attrib["cy"]))
        if "data-net" in group.attrib:
            name = group.attrib["data-net"]
            routes[name] = []
            for wire in group.findall(uri+"polyline"):
                vertices = [pixels(*map(float,p.split(","))) for p in wire.attrib["points"].split()]
                routes[name].append({"from": wire.attrib["data-from"], "to": wire.attrib["data-to"],
                                     "vertices_px": vertices})
    # Pin positions come from the same SVG marks used by the guide. Abort if
    # serialized model coordinates and wire endpoints disagree at screen precision.
    for name, connections in nets.items():
        if len(routes[name]) != len(connections):
            raise ValueError("guide lost a model connection")
        for observed,(src,dst,_) in zip(routes[name], connections):
            if (observed["from"], observed["to"]) != (src,dst):
                raise ValueError("guide/model endpoint mismatch")
            if any(abs(v-q)>0.05 for actual, expected in ((observed["vertices_px"][0],pins[src]),
                    (observed["vertices_px"][-1],pins[dst])) for v,q in zip(actual,expected)):
                raise ValueError("SVG rounding exceeds guide registration precision")
    return (ET.tostring(outer,encoding="utf-8",xml_declaration=True),
            {"canvas_px":list(CANVAS),"coordinate_system":"top-left origin, positive Y down",
             "fiducials_px":MARKS,"sheet_px_per_mm":scale,"pins_px":pins,"nets":routes})


def rasterize(vector, requested=None):
    if requested in (None,"cairosvg"):
        try:
            import cairosvg
        except ImportError:
            if requested == "cairosvg":
                raise ValueError("original CairoSVG renderer is unavailable")
        else:
            return cairosvg.svg2png(bytestring=vector), {"name":"cairosvg","version":cairosvg.__version__}
    if requested not in (None,"inkscape") or not shutil.which("inkscape"):
        raise ValueError("a supported SVG rasterizer is required")
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp)/"guide.svg"
        target = Path(tmp)/"guide.png"
        source.write_bytes(vector)
        try:
            version = subprocess.check_output(["inkscape","--version"],text=True,timeout=10).strip()
            subprocess.run(["inkscape",str(source),"--export-type=png",f"--export-filename={target}"],
                           capture_output=True,check=True,timeout=30)
        except subprocess.SubprocessError as error:
            raise ValueError("Inkscape failed to render the local drawing") from error
        return target.read_bytes(), {"name":"inkscape","version":version}


def guide_files(raw, svg, nets, renderer=None):
    vector, controls = registered_sheet(svg,nets)
    raster, tool = rasterize(vector,renderer)
    # Normalize encoder metadata (e.g. date fields) to bind identical decoded pixels.
    with Image.open(io.BytesIO(raster)) as src:
        normalized = io.BytesIO()
        if src.size != CANVAS:
            raise ValueError("guide raster has unexpected pixel dimensions")
        src.convert("RGB").save(normalized,format="PNG",compress_level=6)
        raster = normalized.getvalue()
    controls.update({"schema":"merlin-draft-control/1","source_sha256":digest(raw),"svg_sha256":digest(svg),
                     "guide_sha256":digest(raster),"renderer":tool})
    lines = [
        "Edit the supplied conditioning-guide.png. Keep the 1536 × 1024 landscape composition.",
        "Treat the source as a dimensioned master. Preserve the four labeled registration crosses A–D, "
        "component outlines, pin circles, exact text, net paths, right-angle bends and endpoint positions.",
        "Limit your edit to small changes in paper grain and pen texture. Keep every existing edge readable.",
        "Each route below lists its vertices in guide pixels, measured from the top left.",
    ]
    for name, routes in controls["nets"].items():
        for route in routes:
            lines.append(f"{name}: {route['from']} to {route['to']} at {route['vertices_px']}.")
    lines.append("Keep the same number of components, wires, junctions and labels. Return one edited PNG.")
    return {"conditioning-guide.png":raster,"draft-controls.json":(json.dumps(controls,indent=2)+"\n").encode(),
            "image-edit-brief.txt":("\n".join(lines)+"\n").encode()}


def json_object(raw):
    def unique_pairs(pairs):
        result = {}
        for k,v in pairs:
            if k in result:
                raise ValueError(f"duplicate review field {k}")
            result[k] = v
        return result
    value = json.loads(raw,object_pairs_hook=unique_pairs)
    if not isinstance(value,dict):
        raise ValueError("review record must be an object")
    return value


def verdict_status(verdict, controls, image_sha):
    expected_hashes = {k:controls[k] for k in ("source_sha256","guide_sha256")}
    expected_hashes["image_sha256"] = image_sha
    if verdict.get("schema") != "merlin-drafting-verdict/1" or any(
            verdict.get(k) != v for k,v in expected_hashes.items()):
        raise ValueError("review schema or source/guide/image digest mismatch")
    for key in ("reviewer","notes"):
        value = verdict.get(key)
        if not isinstance(value,str) or not value.strip() or len(value)>4000:
            raise ValueError(f"review requires {key}")
    checks = verdict.get("checks")
    if not isinstance(checks,dict) or set(checks)!=set(CHECKS):
        raise ValueError("review must cover every global check exactly once")
    states = list(checks.values())
    rows = verdict.get("nets")
    if not isinstance(rows,list):
        raise ValueError("missing net reviews")
    unseen = set(controls["nets"])
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get("id"),str) or row["id"] not in unseen:
            raise ValueError("unknown or repeated reviewed net")
        name = row["id"]
        unseen.remove(name)
        states.append(row.get("status"))
        missing = {(r["from"],r["to"]) for r in controls["nets"][name]}
        if not isinstance(row.get("connections"),list):
            raise ValueError("missing connection reviews")
        for conn in row["connections"]:
            if not isinstance(conn,dict) or not all(isinstance(conn.get(k),str) for k in ("from","to")):
                raise ValueError("invalid reviewed connection")
            pair = conn["from"],conn["to"]
            if pair not in missing:
                raise ValueError("unknown, reversed or repeated reviewed connection")
            missing.remove(pair)
            states.append(conn.get("status"))
        if missing:
            raise ValueError("missing connection review")
    if unseen or any(s not in STATES for s in states):
        raise ValueError("incomplete net review or invalid status")
    return "accepted" if all(s=="pass" for s in states) else "rejected"


def review_wiring(source, guide_dir, image, verdict_file, destination):
    raw = limited(source,131072)
    title,_,parts,pins,nets = read_sheet(raw)
    svg = wire_svg(title,parts,pins,nets)
    controls = json_object(limited(guide_dir/"draft-controls.json",2_000_000))
    tool = controls.get("renderer")
    if not isinstance(tool,dict) or tool.get("name") not in ("cairosvg","inkscape"):
        raise ValueError("unknown guide renderer")
    rebuilt = guide_files(raw,svg,nets,tool["name"])
    if any(limited(guide_dir/name,16_000_000) != content for name,content in rebuilt.items()):
        raise ValueError("control package differs from reconstructed source")
    if limited(guide_dir/"wiring.svg",4_000_000)!=svg:
        raise ValueError("sheet differs from reconstructed source")
    candidate = limited(image,32_000_000)
    try:
        with Image.open(io.BytesIO(candidate)) as asset:
            if asset.format != "PNG" or asset.width * asset.height > 24_000_000 or asset.n_frames != 1:
                raise ValueError("expected a single bounded PNG candidate")
            size = asset.size
            asset.verify()
        with Image.open(io.BytesIO(candidate)) as asset:
            asset.load()
    except (Image.DecompressionBombError, SyntaxError) as error:
        raise ValueError("candidate PNG could not be verified") from error
    image_sha = digest(candidate)
    verdict_raw = limited(verdict_file,300_000)
    verdict = json_object(verdict_raw)
    decision = verdict_status(verdict,controls,image_sha)
    if size[0]*CANVAS[1]!=size[1]*CANVAS[0]:
        decision = "rejected"
    result = {"schema":"merlin-drafting-review/1","decision":decision,"reviewer":verdict["reviewer"],
              "source_sha256":digest(raw),"guide_sha256":controls["guide_sha256"],"image_sha256":image_sha,
              "verdict_sha256":digest(verdict_raw),"size_px":list(size),
              "aspect_ratio_matches":size[0]*CANVAS[1]==size[1]*CANVAS[0],"checks":verdict["checks"],
              "nets":verdict["nets"],"notes":verdict["notes"],"authority":"illustration review only"}
    destination.mkdir()
    try:
        (destination/"review.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    except OSError:
        shutil.rmtree(destination)
        raise
    return result
