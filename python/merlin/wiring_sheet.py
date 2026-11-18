"""Measured single-plane signal drawing. Input coordinates are explicit millimetres."""
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET

GRID = 1000  # integer micrometres per millimetre


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", value):
        raise ValueError("identifiers must be 1–32 ASCII letters, digits, underscores or hyphens")
    return value


def caption(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 160 or not value.isprintable():
        raise ValueError("expected a printable caption of at most 160 characters")
    return value


def entries(obj, key, limit, minimum=1):
    if not isinstance(obj, dict) or not isinstance(obj.get(key), list) or not minimum <= len(obj[key]) <= limit:
        raise ValueError(f"expected {minimum} to {limit} {key}")
    return obj[key]


def coord(value):
    if type(value) not in (Decimal, int) or not Decimal(value).is_finite():
        raise ValueError("coordinate must be a finite millimetre value")
    n = Decimal(value)
    if n.copy_abs() > 100000 or (n and n.copy_abs() < Decimal("0.001")):
        raise ValueError("coordinate exceeds bounds or micrometre resolution")
    numerator, denominator = n.as_integer_ratio()
    scaled, remainder = divmod(numerator * GRID, denominator)
    if remainder:
        raise ValueError("coordinate falls between micrometres")
    return scaled


def point(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("expected two coordinates")
    return tuple(map(coord, value))


def intersects(first, second):
    (ax, ay), (bx, by) = first
    (cx, cy), (dx, dy) = second
    return (max(min(ax,bx), min(cx,dx)) <= min(max(ax,bx), max(cx,dx))
            and max(min(ay,by), min(cy,dy)) <= min(max(ay,by), max(cy,dy)))


def inside_body(segment, box):
    (x,y), (u,v) = segment
    left, bottom, right, top = box
    if x == u:
        return left < x < right and max(min(y,v),bottom) < min(max(y,v),top)
    return bottom < y < top and max(min(x,u),left) < min(max(x,u),right)


def unique(name, seen):
    key = name.casefold()
    if key in seen:
        raise ValueError(f"duplicate identifier: {name}")
    seen.add(key)


def read_sheet(raw):
    spec = json.loads(raw, parse_float=Decimal)
    if not isinstance(spec, dict) or spec.get("unit") != "mm":
        raise ValueError("expected unit mm")
    title = caption(spec.get("title"))
    reference = None
    if "reference_image" in spec:
        image = spec["reference_image"]
        if not isinstance(image, dict):
            raise ValueError("reference_image must contain title, source and credit")
        reference = {key: caption(image.get(key)) for key in ("title", "source", "credit")}
    components, pins, occupied = {}, {}, set()
    component_names = set()
    for component in entries(spec, "components", 48):
        if not isinstance(component, dict):
            raise ValueError("invalid component")
        name = identifier(component.get("id"))
        unique(name, component_names)
        x,y = point(component.get("origin"))
        w,h = point(component.get("size"))
        if min(w,h) <= 0:
            raise ValueError("component size must be positive")
        box = (x,y,x+w,y+h)
        if any(max(x,a)<min(x+w,c) and max(y,b)<min(y+h,d) for a,b,c,d in components.values()):
            raise ValueError("component interiors overlap")
        components[name] = box
        pin_names = set()
        for pin in entries(component,"pins",24):
            if not isinstance(pin, dict):
                raise ValueError("invalid pin")
            p = identifier(pin.get("id"))
            unique(p, pin_names)
            dx,dy = point(pin.get("offset"))
            if not (0<=dx<=w and 0<=dy<=h and (dx in (0,w) or dy in (0,h))):
                raise ValueError("pin must lie on component boundary")
            location = x+dx,y+dy
            if location in occupied:
                raise ValueError("pins must have distinct locations")
            occupied.add(location)
            pins[f"{name}.{p}"] = location
    nets, occupied_segments, pin_nets = {}, [], {}
    net_names = set()
    for net in entries(spec,"nets",64):
        if not isinstance(net,dict):
            raise ValueError("invalid net")
        name = identifier(net.get("id"))
        unique(name, net_names)
        graph, routes, segments = {}, [], []
        for route in entries(net,"routes",64):
            if not isinstance(route,dict):
                raise ValueError("invalid route")
            src, dst = route.get("from"), route.get("to")
            if not all(isinstance(k,str) and k in pins for k in (src,dst)) or src == dst:
                raise ValueError("route must connect two distinct known pins")
            for endpoint in (src,dst):
                if pin_nets.setdefault(endpoint,name) != name:
                    raise ValueError("a pin cannot be shared by separate nets")
            points = list(map(point,entries(route,"points",64,2)))
            if (points[0],points[-1]) != (pins[src],pins[dst]):
                raise ValueError("named pins and route endpoints disagree")
            if dst in graph.setdefault(src,set()):
                raise ValueError("duplicate pin-pair route")
            graph[src].add(dst)
            graph.setdefault(dst,set()).add(src)
            if len(segments)+len(occupied_segments)+len(points)-1 > 1024:
                raise ValueError("drawing exceeds 1024 route segments")
            for a,b in zip(points,points[1:]):
                if (a[0]==b[0]) == (a[1]==b[1]):
                    raise ValueError("routes require nonzero horizontal or vertical segments")
                seg = a,b
                if any(inside_body(seg,box) for box in components.values()):
                    raise ValueError("route enters a component interior")
                if any(intersects(seg,prev) for prev in occupied_segments):
                    raise ValueError("different nets touch or cross on the drawing plane")
                if any(k not in (src,dst) and intersects(seg,(v,v)) for k,v in pins.items()):
                    raise ValueError("route touches an undeclared pin")
                segments.append(seg)
            routes.append((src,dst,points))
        reached, frontier = set(), [next(iter(graph))]
        while frontier:
            current = frontier.pop()
            if current not in reached:
                reached.add(current)
                frontier.extend(graph[current]-reached)
        if len(reached) != len(graph):
            raise ValueError("net contains disconnected pin groups")
        nets[name] = routes
        occupied_segments.extend(segments)
    return title, reference, components, pins, nets


def mm(pt):
    return tuple(n / GRID for n in pt)


def wire_svg(title, components, pins, nets):
    coords=[p for routes in nets.values() for _,_,points in routes for p in points]
    coords.extend(point for x,y,u,v in components.values() for point in ((x,y),(u,v)))
    xs,ys=zip(*(mm(p) for p in coords))
    left,right,bottom,top=min(xs)-8,max(xs)+8,min(ys)-12,max(ys)+17
    width,height=right-left,top-bottom
    root=ET.Element("svg",xmlns="http://www.w3.org/2000/svg",width=f"{width:g}mm",
                    height=f"{height:g}mm",viewBox=f"0 0 {width:g} {height:g}",role="img")
    ET.SubElement(root,"title").text=title
    def xy(pt):
        x,y=mm(pt)
        return x-left,top-y
    def tag(parent,kind,**attrs):
        return ET.SubElement(parent,kind,{key.replace("_","-"):str(val) for key,val in attrs.items()})
    def label(parent,x,y,text,size,**attrs):
        tag(parent,"text",x=x,y=y,font_size=size,fill="#273e48",**attrs).text=text
    tag(root,"rect",width=width,height=height,fill="#faf7ed")
    defs=tag(root,"defs")
    grid=tag(defs,"pattern",id="grid",width=5,height=5,patternUnits="userSpaceOnUse")
    tag(grid,"path",d="M 5 0 H 0 V 5",fill="none",stroke="#dddcca",stroke_width=".15")
    tag(root,"rect",width=width,height=height,fill="url(#grid)")
    label(root,7,8,title,4.2,font_family="serif",font_style="italic")
    for name,(x,y,u,v) in components.items():
        g=tag(root,"g",data_component=name)
        a,b=xy((x,v))
        tag(g,"rect",x=a,y=b,width=(u-x)/GRID,height=(v-y)/GRID,rx=".65",
            fill="#fbfaef",stroke="#263e48",stroke_width=".45")
        label(g,a+(u-x)/GRID/2,b+(v-y)/GRID/2+1,name,2.9,text_anchor="middle",font_family="serif")
    for name,routes in nets.items():
        g=tag(root,"g",data_net=name)
        for src,dst,points in routes:
            path=" ".join(f"{x:g},{y:g}" for x,y in map(xy,points))
            tag(g,"polyline",data_from=src,data_to=dst,points=path,fill="none",stroke="#146564",
                stroke_width=".55",stroke_linejoin="round")
        a,b=map(xy,routes[0][2][:2])
        label(g,(a[0]+b[0])/2,(a[1]+b[1])/2-1.5,name,1.9,font_family="monospace",text_anchor="middle")
    for name,p in pins.items():
        parent,pin=name.split(".")
        x,y=xy(p)
        lo,_,hi,_=components[parent]
        anchor="end" if p[0]==lo else "start"
        shift=-.9 if p[0]==lo else .9
        g=tag(root,"g",data_pin=name)
        tag(g,"circle",cx=x,cy=y,r=".7",stroke="#263e48",fill="#fbfaef",stroke_width=".35")
        label(g,x+shift,y+3.2,pin,1.6,text_anchor=anchor,font_family="monospace")
    label(root,7,height-4,"SIGNAL ROUTING STUDY   /   mm",1.9,font_family="monospace")
    return ET.tostring(root,encoding="utf-8",xml_declaration=True)


def wire_dxf(components,pins,nets,path):
    # Called only by the short-lived CAD writer worker, keeping ezdxf's metadata
    # mode process-local and preserving other drawing writers' settings.
    import ezdxf
    ezdxf.options.write_fixed_meta_data_for_testing=True
    doc=ezdxf.new("R2010",units=ezdxf.units.MM)
    doc.appids.add("MERLIN")
    space=doc.modelspace()
    for layer in ["COMPONENTS","PINS","LABELS",*("NET_"+name for name in nets)]:
        doc.layers.add(layer)
    def text(value,pt):
        space.add_text(value,height=2,dxfattribs={"layer":"LABELS","insert":pt})
    for name,(x,y,u,v) in components.items():
        space.add_lwpolyline([mm(p) for p in ((x,y),(u,y),(u,v),(x,v))],close=True,
                             dxfattribs={"layer":"COMPONENTS"})
        text(name,mm((x+GRID,y+GRID*2)))
    for name,pt in pins.items():
        x,y=mm(pt)
        entity = space.add_circle((x,y),radius=.7,dxfattribs={"layer":"PINS"})
        entity.set_xdata("MERLIN", [(1000, name)])
        text(name,(x+1,y+1))
    for name,routes in nets.items():
        for src, dst, points in routes:
            wire = space.add_lwpolyline(list(map(mm,points)),dxfattribs={"layer":"NET_"+name})
            wire.set_xdata("MERLIN", [(1000, name), (1000, src), (1000, dst)])
    doc.saveas(path)


def render_wiring(source,destination):
    import os
    import subprocess
    import sys
    with source.open("rb") as stream:
        raw=stream.read(131073)
    if len(raw)>131072:
        raise ValueError("input exceeds 128 KiB")
    title,ref,parts,pins,nets=read_sheet(raw)
    if destination.exists():
        raise FileExistsError(destination)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        stage=Path(temp)
        (stage/"wiring.svg").write_bytes(wire_svg(title,parts,pins,nets))
        try:
            child = subprocess.run(
                [sys.executable, "-m", "merlin.wiring_sheet", str(stage / "wiring.dxf")],
                input=raw, capture_output=True, timeout=30,
                env={**os.environ, "PYTHONHASHSEED": "0"},
            )
        except subprocess.TimeoutExpired as error:
            raise ValueError("CAD writer exceeded its 30-second budget") from error
        if child.returncode:
            raise ValueError("CAD writer failed: "+child.stderr.decode("utf-8",errors="replace")[-450:])
        connections=[{"net":name,"from":src,"to":dst,"length_mm":sum(
            abs(a[0]-b[0])+abs(a[1]-b[1]) for a,b in zip(points,points[1:]))/GRID}
                     for name,routes in nets.items() for src,dst,points in routes]
        brief=["Draw a hand-drafted scientific signal diagram on cream graph paper.",
               "Use ink lines and readable labels. Follow these component and net names exactly."]
        brief.extend(f"{row['net']}: {row['from']} to {row['to']}." for row in connections)
        brief.append("Show only these logical connections. Leave dimensions and physical pin assignments to the measured drawing.")
        (stage/"image-brief.txt").write_text("\n".join(brief)+"\n",encoding="utf-8")
        hashes={key:sha256((stage/key).read_bytes()).hexdigest() for key in ("wiring.svg","wiring.dxf","image-brief.txt")}
        receipt={"schema":"merlin-wiring-sheet/1","title":title,"unit":"mm","source_sha256":sha256(raw).hexdigest(),
                 "connections":connections,"reference_image":ref,"artifact_sha256":hashes,
                 "limits":"Explicit single-plane drawing. Physical clearance, circuit behavior and fabrication readiness are unassessed."}
        (stage/"receipt.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
        destination.mkdir()
        try:
            for path in stage.iterdir():
                path.rename(destination/path.name)
        except OSError:
            shutil.rmtree(destination)
            raise
    return receipt


if __name__=="__main__":
    import sys
    title,reference,parts,pins,nets=read_sheet(sys.stdin.buffer.read(131073))
    wire_dxf(parts,pins,nets,sys.argv[1])
