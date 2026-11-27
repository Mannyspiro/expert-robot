"""Build and record a declarative Merlin scene with Blender. No model-written Python is loaded."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


def number(x,low,high,label):
    if type(x) not in (int,float) or not math.isfinite(x) or not low<=x<=high:
        raise ValueError(f"{label} must be a number between {low} and {high}")
    return x


def vec(x,low,high,label):
    if not isinstance(x,list) or len(x)!=3:
        raise ValueError(f"{label} must have three coordinates")
    return tuple(number(y,low,high,label) for y in x)


def named(items):
    values=[x["name"] for x in items]
    if any(not isinstance(x,str) or not x.strip() for x in values) or len(values)!=len(set(values)):
        raise ValueError("Every object needs a unique name")
    return dict(zip(values,items))


def load(source):
    spec=json.loads(source.read_text(encoding="utf-8"))
    if spec["version"]!=1:
        raise ValueError("Use scene specification version 1")
    res=spec["resolution"]
    if not isinstance(res,list) or len(res)!=2 or any(type(x)!=int or not 128<=x<=2560 for x in res):
        raise ValueError("Resolution is a pair of integers from 128 to 2560")
    for k,minv,maxv in (("fps",1,60),("frames",1,3600)):
        if type(spec[k])!=int or not minv<=spec[k]<=maxv:
            raise ValueError(f"{k} must be an integer from {minv} to {maxv}")
    if not spec["objects"] or len(spec["objects"])>160:
        raise ValueError("Use between one and 160 scene objects")
    objects=named(spec["objects"])
    if not spec["subjects"] or not set(spec["subjects"]).issubset(objects):
        raise ValueError("Name at least one visible subject from the object list")
    return spec


def shader(name,s,root):
    if "library" in s:
        relative=Path(s["library"])
        lib=(root/relative).resolve()
        if relative.is_absolute() or not lib.is_relative_to(root) or lib.suffix!=".blend" or not lib.is_file():
            raise ValueError(f"{name}: choose an existing .blend library inside the specification folder")
        asset=s["asset"]
        with bpy.data.libraries.load(str(lib),link=False) as (available,wanted):
            if asset not in available.materials:
                raise ValueError(f"{name}: no material named {asset} in {relative}")
            wanted.materials=[asset]
        return wanted.materials[0]
    m=bpy.data.materials.new(name)
    m.use_nodes=True
    color=vec(s["color"],0,1,"Base color")
    m.diffuse_color=(*color,1)
    for key,opt,default in (("Roughness","roughness",.52),("Metallic","metallic",0)):
        m.node_tree.nodes["Principled BSDF"].inputs[key].default_value=number(s.get(opt,default),0,1,opt)
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value=(*color,1)
    return m


def transform(o,s):
    if "at" in s:
        o.location=vec(s["at"],-200,200,"Object position")
    if "rotation" in s:
        o.rotation_euler=tuple(math.radians(x) for x in vec(s["rotation"],-1440,1440,"Euler rotation"))


def posekeys(o,poses,limit,callback,properties):
    previous=0
    for p in poses:
        frame=p["frame"]
        if type(frame)!=int or not previous<frame<=limit:
            raise ValueError(f"{o.name}: keyframes must be increasing within the scene")
        callback(o,p)
        for prop in properties:
            o.keyframe_insert(data_path=prop,frame=frame)
        previous=frame


def mesh(s,mats,limit):
    builders={"cube":lambda:bpy.ops.mesh.primitive_cube_add(size=1),
              "sphere":lambda:bpy.ops.mesh.primitive_uv_sphere_add(segments=40,ring_count=24),
              "cylinder":lambda:bpy.ops.mesh.primitive_cylinder_add(vertices=48)}
    kind=s["shape"]
    if kind not in builders:
        raise ValueError(f"Unsupported shape {kind}")
    builders[kind]()
    o=bpy.context.object
    o.name=s["name"]
    o.dimensions=vec(s["size"],.02,250,"Object size")
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    transform(o,s)
    if kind=="sphere":
        for p in o.data.polygons:p.use_smooth=True
    bevel=number(s.get("bevel",0),0,1,"Bevel")
    if bevel:
        b=o.modifiers.new("Reflected edge","BEVEL")
        b.width=bevel
        b.segments=3
    o.data.materials.append(mats[s["material"]])
    posekeys(o,s.get("keys",[]),limit,transform,("location","rotation_euler"))
    return o


def aim(o,s):
    transform(o,s)
    target=Vector(vec(s["target"],-200,200,"Target"))
    forward=target-o.location
    if forward.length<.001:
        raise ValueError("Target must differ from object position")
    o.rotation_euler=forward.to_track_quat("-Z","Y").to_euler()


def build(spec,root,quality):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc=bpy.context.scene
    sc.name=spec["name"]
    sc.render.fps=spec["fps"]
    sc.frame_end=spec["frames"]
    sc.render.resolution_x,sc.render.resolution_y=spec["resolution"]
    sc.render.resolution_percentage=100 if quality=="final" else 50
    sc.render.engine="CYCLES"
    sc.cycles.device="CPU"
    sc.cycles.samples=72 if quality=="final" else 12
    sc.cycles.use_denoising=False
    sc.view_settings.view_transform="AgX"
    sc.render.image_settings.file_format="PNG"
    sc.render.image_settings.color_mode="RGB"
    world=bpy.data.worlds.new("Studio fill")
    world.use_nodes=True
    world.node_tree.nodes["Background"].inputs["Color"].default_value=(.17,.18,.27,1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value=.38
    sc.world=world
    mats={n:shader(n,e,root) for n,e in spec["materials"].items()}
    items={s["name"]:mesh(s,mats,sc.frame_end) for s in spec["objects"]}
    bpy.ops.object.camera_add()
    camera=bpy.context.object
    sc.camera=camera
    camera.name="Merlin camera"
    c=spec["camera"]
    camera.data.lens=number(c.get("lens",45),16,160,"Camera lens")
    if "orthographic" in c:
        camera.data.type="ORTHO"
        camera.data.ortho_scale=number(c["orthographic"],.25,60,"Orthographic scale")
    aim(camera,c)
    posekeys(camera,c.get("keys",[]),sc.frame_end,aim,("location","rotation_euler"))
    for entry in spec["lights"]:
        bpy.ops.object.light_add(type="AREA")
        o=bpy.context.object
        o.name=entry["name"]
        o.data.energy=number(entry["power"],0,4000,"Light power")
        o.data.color=vec(entry["color"],0,1,"Light color")
        o.data.size=number(entry["size"],.05,30,"Light size")
        aim(o,entry)
    return sc,items


def framing(sc,items,names,frames):
    margin=1.0
    # Project the eight subject bounds into the real camera at each selected frame.
    for frame in frames:
        sc.frame_set(frame)
        for name in names:
            o=items[name]
            for corner in o.bound_box:
                point=world_to_camera_view(sc,sc.camera,o.matrix_world@Vector(corner))
                if point.z<=0:
                    raise ValueError(f"{name} fell behind the camera at frame {frame}")
                margin=min(margin,point.x,1-point.x,point.y,1-point.y)
                if min(point.x,1-point.x,point.y,1-point.y)<.025:
                    raise ValueError(f"{name} is too near the frame edge at frame {frame}. Adjust camera or size.")
    return margin


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--spec",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--mode",choices=("build","preview","sequence"),default="preview")
    p.add_argument("--quality",choices=("draft","final"),default="draft")
    p.add_argument("--start",type=int,default=1);p.add_argument("--end",type=int)
    p.add_argument("--step",type=int,default=1)
    args=p.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    source=args.spec.resolve()
    spec=load(source)
    end=args.end if args.end is not None else (args.start if args.mode=="preview" else spec["frames"])
    if not 1<=args.start<=end<=spec["frames"] or args.step<1:
        raise ValueError("Requested frames are outside the scene")
    frames=list(range(args.start,end+1,args.step))
    sc,items=build(spec,source.parent,args.quality)
    margin=framing(sc,items,spec["subjects"],frames)
    out=args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise FileExistsError("Pick a new output directory for the render")
    out.mkdir(exist_ok=True,parents=True)
    sc.frame_set(args.start)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(out/"Merlin_Scene.blend"))
    rendered=[]
    if args.mode!="build":
        for i,f in enumerate(frames,1):
            sc.frame_set(f)
            path=out/("preview.png" if args.mode=="preview" and len(frames)==1 else f"frame_{i:04}.png")
            sc.render.filepath=str(path)
            bpy.ops.render.render(write_still=True)
            rendered.append({"image":path.name,"blender_frame":f})
    receipt={"name":spec["name"],"blender":bpy.app.version_string,"minimum_framing_margin":round(margin,4),
             "frames_checked":len(frames),"fps":spec["fps"],"files":rendered,"quality":args.quality}
    (out/"Render_Receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print("Merlin scene verified:",out,flush=True)


if __name__=="__main__":
    main()
