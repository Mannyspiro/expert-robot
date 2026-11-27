"""Build and record an editable cinematic forest in Blender."""

import argparse
from math import cos, sin, pi
from pathlib import Path
import random
import sys

import bpy
from mathutils import Vector


TAU=2*pi
rng=random.Random(7538)

def material(name,color,rough=.8,emission=0):
    mat=bpy.data.materials.new(name)
    mat.diffuse_color=(*color,1)
    mat.use_nodes=True
    p=mat.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value=(*color,1)
    p.inputs["Roughness"].default_value=rough
    p.inputs["Emission Color"].default_value=(*color,1)
    p.inputs["Emission Strength"].default_value=emission
    return mat


def ground_color(a,b):
    mat=material("Moss and dark earth",a)
    nodes=mat.node_tree.nodes
    links=mat.node_tree.links
    n=nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value=2
    n.inputs["Detail"].default_value=3
    tex=nodes.new("ShaderNodeTexCoord")
    links.new(tex.outputs["Object"],n.inputs["Vector"])
    c=nodes.new("ShaderNodeValToRGB")
    c.color_ramp.elements[0].position=.20
    c.color_ramp.elements[0].color=(*a,1)
    c.color_ramp.elements[1].position=.83
    c.color_ramp.elements[1].color=(*b,1)
    links.new(n.outputs["Fac"],c.inputs["Fac"])
    p=nodes.get("Principled BSDF")
    links.new(c.outputs["Color"],p.inputs["Base Color"])
    bump=nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value=.26
    bump.inputs["Distance"].default_value=.09
    links.new(n.outputs["Fac"],bump.inputs["Height"])
    links.new(bump.outputs["Normal"],p.inputs["Normal"])
    return mat


def mesh(name,verts,faces,mats):
    data=bpy.data.meshes.new(name)
    data.from_pydata(verts,[],faces)
    data.update()
    obj=bpy.data.objects.new(name,data)
    bpy.context.collection.objects.link(obj)
    for m in mats:
        data.materials.append(m)
    return obj


def ground(x,y):
    return .15*sin(.74*x+.20*y)+.12*cos(.55*y)+.07*sin(1.1*x+.9*y)


def trail(y):
    return .52*sin(.20*y)-.035*y


def terrain(earth,path):
    span=45
    verts=[(x,y,ground(x,y)) for y in range(-9,36) for x in range(-22,23)]
    faces=[(i,i+1,i+span+1,i+span) for i in range(span*(span-1)) if i%span<span-1]
    obj=mesh("Uneven forest floor",verts,faces,[earth])
    for f in obj.data.polygons:
        f.use_smooth=True
    verts=[]
    for j in range(143):
        y=-8+j*.30
        for i in range(5):
            x=trail(y)+(i-2)*(.48+.03*sin(y))
            verts.append((x,y,ground(x,y)+.018))
    faces=[(i,i+1,i+6,i+5) for i in range(len(verts)-5) if i%5<4]
    obj=mesh("Winding shale footpath",verts,faces,[path])
    for f in obj.data.polygons:
        f.use_smooth=True


def tapered(name,rings,mats,sides=8):
    verts=[(x+r*cos(TAU*i/sides),y+r*sin(TAU*i/sides),z)
           for x,y,z,r in rings for i in range(sides)]
    faces=[tuple(reversed(range(sides)))]
    for layer in range(len(rings)-1):
        for i in range(sides):
            a=layer*sides+i
            b=layer*sides+(i+1)%sides
            faces.append((a,b,b+sides,a+sides))
    faces.append(tuple(range(len(verts)-sides,len(verts))))
    obj=mesh(name,verts,faces,mats)
    for face in obj.data.polygons:
        face.material_index=(face.index%7==3) if len(mats)>1 else 0
    return obj


def tree(name,x,y,h,rad,bark,greens):
    z=ground(x,y)
    dx,dy=rng.uniform(-.65,.65),rng.uniform(-.65,.65)
    tapered(name+" trunk",[(x,y,z,rad*1.55),(x,y,z+.72,rad),
        (x+dx*.35,y+dy*.35,z+.48*h,rad*.60),(x+dx,y+dy,z+h,rad*.09)],bark,7)
    for tier in range(5):
        level=.38+.12*tier
        spread=rad*4.5*(1-tier*.135)+.44
        verts=[]
        faces=[]
        for branch in range(7):
            theta=TAU*(branch/7)+.75*tier
            offx,offy=cos(theta),sin(theta)
            fx=x+dx*level
            fy=y+dy*level
            fz=z+h*level
            ext=spread*rng.uniform(.81,1.20)
            for j in range(3):
                scale=1-j*.19
                rise=(j-.7)*.27
                th=theta+(j-1)*.29
                i=len(verts)
                verts += [(fx,fy,fz+rise),(fx+cos(th-.25)*ext*.77*scale,fy+sin(th-.25)*ext*.77*scale,fz+rise-.27),
                          (fx+cos(th)*ext*scale,fy+sin(th)*ext*scale,fz+rise-.43),
                          (fx+cos(th+.25)*ext*.77*scale,fy+sin(th+.25)*ext*.77*scale,fz+rise-.22),
                          (fx+offx*ext*.46,fy+offy*ext*.46,fz+rise+.40)]
                faces += [(i,i+1,i+4),(i+1,i+2,i+4),(i+2,i+3,i+4),(i+3,i,i+4)]
        crown=mesh(name+" crown",verts,faces,greens)
        for face in crown.data.polygons:
            face.material_index=rng.choices(range(3),[.48,.36,.16])[0]


def fern(x,y,scale,green):
    z=ground(x,y)
    verts=[]
    faces=[]
    for blade in range(6):
        angle=TAU*blade/6+rng.random()*.5
        right=(-sin(angle),cos(angle))
        for pair in range(1,7):
            t=pair/7
            span=scale*.18*sin(pi*t)
            px=x+cos(angle)*t*scale
            py=y+sin(angle)*t*scale
            z1=z+scale*(.1+.53*sin(pi*t*.9))
            idx=len(verts)
            verts.extend([(px,py,z1),
                (px+span*right[0],py+span*right[1],z1+.04),
                (px+cos(angle)*scale*.18,py+sin(angle)*scale*.18,z1+.08),
                (px-span*right[0],py-span*right[1],z1+.04)])
            faces.extend([(idx,idx+1,idx+2),(idx,idx+2,idx+3)])
    mesh("Fern",verts,faces,[green])


def rock(name,x,y,z,scale,mat):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=1,location=(x,y,z))
    ob=bpy.context.object
    ob.name=name
    ob.scale=scale
    ob.rotation_euler=(rng.random(),rng.random(),rng.random()*pi)
    ob.data.materials.append(mat)
    return ob


def area(name,pos,aim,power,color,size):
    light=bpy.data.lights.new(name,"AREA")
    light.energy=power
    light.shape="DISK"
    light.size=size
    light.color=color
    obj=bpy.data.objects.new(name,light)
    bpy.context.collection.objects.link(obj)
    obj.location=pos
    obj.rotation_euler=(Vector(aim)-obj.location).to_track_quat("-Z","Y").to_euler()
    return obj


def camera(scene):
    positions=[
      (1, (-.33,-5.8,1.52),(.28,5.9,1.87),43),
      (48,( .17,-3.8,1.70),(.00,7.8,2.05),43),
      (49,(-2.32,2.2,.92),(.21,11.0,1.57),40),
      (96,(-1.84,4.2,1.00),(.31,12.0,1.50),43),
      (97,( .52,5.75,1.67),(.41,15.0,2.18),37),
      (144,(.42,8.35,1.95),(.46,15.0,2.04),39),
    ]
    data=bpy.data.cameras.new("Cinema camera")
    obj=bpy.data.objects.new("Cinema camera",data)
    bpy.context.collection.objects.link(obj)
    scene.camera=obj
    def key(camera,poses):
        for frame,pos,aim,lens in poses:
            camera.location=pos
            camera.rotation_euler=(Vector(aim)-camera.location).to_track_quat("-Z","Y").to_euler()
            camera.keyframe_insert(data_path="location",frame=frame)
            camera.keyframe_insert(data_path="rotation_euler",frame=frame)
            camera.data.lens=lens
            camera.data.keyframe_insert(data_path="lens",frame=frame)
    key(obj,positions)
    insert=bpy.data.objects.new("Low trail camera",bpy.data.cameras.new("Low trail camera"))
    bpy.context.collection.objects.link(insert)
    key(insert,[(49,(.22,.7,.91),(.20,8.7,1.32),36),
                (96,(.20,3.25,1.04),(.24,11.5,1.53),39)])
    scene.timeline_markers.new("Establishing",frame=1).camera=obj
    scene.timeline_markers.new("Trail height",frame=49).camera=insert
    scene.timeline_markers.new("Relay reveal",frame=97).camera=obj


def build(out, frames, seed, look):
    rng.seed(seed)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene
    scene.name="A Lantern in the Violet Woods"
    scene.render.engine="CYCLES"
    scene.cycles.samples=8
    # This build may lack the optional OpenImageDenoise library.
    scene.cycles.use_denoising=False
    scene.cycles.max_bounces=3
    scene.cycles.preview_samples=8
    scene.render.threads_mode="FIXED"
    scene.render.threads=7
    scene.view_settings.view_transform="AgX"
    scene.view_settings.look="AgX - Medium High Contrast"
    scene.render.resolution_x,scene.render.resolution_y=640,360
    scene.render.resolution_percentage=100
    scene.render.fps=8
    scene.render.image_settings.file_format="PNG"
    scene.render.image_settings.color_mode="RGB"
    scene.frame_start,scene.frame_end=1,144
    scene.render.filepath=str(frames/"frame-")
    world=bpy.data.worlds.new("Cool forest sky")
    scene.world=world
    world.use_nodes=True
    bg=world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value=(.29,.40,.51,1)
    bg.inputs["Strength"].default_value=.67
    world.mist_settings.start=2
    world.mist_settings.depth=31
    scene.view_layers[0].use_pass_mist=True
    scene.use_nodes=True
    nodes=scene.node_tree.nodes
    links=scene.node_tree.links
    nodes.clear()
    source=nodes.new("CompositorNodeRLayers")
    fac=nodes.new("CompositorNodeMath")
    fac.operation="MULTIPLY"
    fac.inputs[1].default_value=.62
    links.new(source.outputs["Mist"],fac.inputs[0])
    mix=nodes.new("CompositorNodeMixRGB")
    mix.inputs[2].default_value=(.23,.34,.43,1)
    links.new(fac.outputs[0],mix.inputs[0])
    links.new(source.outputs["Image"],mix.inputs[1])
    finish=nodes.new("CompositorNodeGlare")
    finish.glare_type="FOG_GLOW"
    finish.quality="MEDIUM"
    finish.threshold=.8
    links.new(mix.outputs[0],finish.inputs["Image"])
    links.new(finish.outputs["Image"],nodes.new("CompositorNodeComposite").inputs["Image"])
    bark=[material("Soot cedar bark",(.056,.035,.030)),material("Cedar ridges",(.14,.115,.086))]
    greens=[material("Ink-green needles",(.024,.086,.076)),material("Misty fir needles",(.049,.17,.134)),
            material("Young needles",(.105,.25,.14))]
    earth=ground_color((.033,.073,.057),(.15,.25,.123))
    path=ground_color((.048,.061,.072),(.22,.21,.168))
    terrain(earth,path)
    for i in range(133):
        x,y=rng.uniform(-20,20),rng.uniform(-7,34)
        if abs(x-trail(y))<1.52 or (abs(x)<3.4 and (y<.5 or 9<y<19)):
            continue
        tree("Fir "+str(i),x,y,rng.uniform(4.1,10.9),rng.uniform(.16,.46),bark,greens)
    for i,(x,y,h,r) in enumerate([(-2.35,-1.5,8.4,.40),(2.7,.7,9.1,.48),(-3.2,7.4,10,.43),
                                  (3.6,10.6,8.1,.35),(-3.45,13.1,6.4,.28),(3.1,3.4,6.6,.36)]):
        tree("Hero cedar "+str(i),x,y,h,r,bark,greens)
    fern_green=material("Fern leaf",(.102,.27,.105))
    for i in range(92):
        y=rng.uniform(-5,23)
        x=trail(y)+(1 if i%2 else -1)*rng.uniform(1.08,6.1)
        fern(x,y,rng.uniform(.27,1.08),fern_green)
    granite=material("Slate boulder",(.11,.13,.16),.95)
    moss=material("Boulder moss",(.071,.15,.096))
    for i in range(90):
        y=rng.uniform(-7,27)
        x=trail(y)+(1 if i%2 else -1)*rng.uniform(.85,6.5)
        size=rng.uniform(.04,.22)
        rock("Shale",x,y,ground(x,y)+size*.32,(1.5*size,size,size*.9),granite if i%3 else moss)
    for x,y,w in [(-2.1,2.8,.62),(2.65,8.6,.48),(-2.56,9.8,.68),(2.9,13.2,.53)]:
        z=ground(x,y)+w*.2
        rock("Mossy boulder",x,y,z,(w*1.3,w,.74*w),granite)
        rock("Moss cap",x+.03,y,z+w*.44,(w,w*.78,.33*w),moss)
    amber=material("Amber glass",(.98,.34,.062),.3,3.0)
    violet=material("Relay violet",(.40,.065,.95),.35,3.6)
    metal=material("Old relay iron",(.08,.10,.14),.58)
    for y in (4.6,10.2,14.6):
        x=trail(y)+1.13
        z=ground(x,y)
        tapered("Trail lantern post",[(x,y,z,.13),(x,y,z+.87,.08)], [metal])
        tapered("Amber lantern",[(x,y,z+.88,.115),(x,y,z+1.13,.09)],[amber])
        area("Lantern spill",(x,y,z+1.25),(x-1,y,z),36,(1,.37,.12),.48)
    y,x=15.0,.44
    z=ground(x,y)
    for mx in (x-1.23,x+1.23):
        tapered("Relay arch pier",[(mx,y,z,.34),(mx,y,z+1.75,.25),(mx*.64,y,z+2.98,.19)],[metal])
        tapered("Relay inset",[(mx,y-.28,z+1.11,.065),(mx,y-.28,z+1.72,.072)],[violet],6)
    tapered("Relay lintel",[(x,y,z+2.78,.9),(x,y,z+3.03,1.04),(x,y,z+3.22,.12)],[metal],6)
    tapered("Violet beacon",[(x,y,z+3.15,.16),(x,y,z+3.54,.03)],[violet])
    area("Relay violet spill",(x,y-.68,z+2.6),(x,y-3,z+.2),130,(.52,.19,1),2.2)
    area("Dawn key",(-8,-1,12),(0,9,1),1600,(1,.65,.38),8)
    area("Blue backlight",(6,21,11),(.5,4,1),2500,(.42,.73,1),10)
    sun=bpy.data.lights.new("Dawn sun","SUN")
    sun.energy=1.8
    sun.color=(1,.76,.54)
    sun.angle=.15
    so=bpy.data.objects.new("Dawn sun",sun)
    bpy.context.collection.objects.link(so)
    so.rotation_euler=(.52,-.52,-.23)
    mote=material("Pollen fireflies",(.96,.76,.23),.40,3.4)
    for i in range(25):
        y=rng.uniform(-2,17)
        x=trail(y)+rng.uniform(-2.2,2.2)
        z=rng.uniform(.8,3.85)
        obj=rock("Drifting pollen",x,y,z,(.017,.017,.017),mote)
        obj.keyframe_insert(data_path="location",frame=1)
        obj.location.x+=rng.uniform(-.48,.48)
        obj.location.z+=rng.uniform(-.24,.48)
        obj.keyframe_insert(data_path="location",frame=144)
    area("Canopy bounce",(-2,6,4),(.5,14,1.5),440,(.63,.85,1),6.5)
    camera(scene)
    if look == "blue-hour":
        bg.inputs["Color"].default_value=(.17,.26,.49,1)
        mix.inputs[2].default_value=(.10,.18,.33,1)
        sun.energy=.42
        sun.color=(.52,.65,1)
        bpy.data.lights["Dawn key"].energy=260
        bpy.data.lights["Blue backlight"].energy=1750
    scene["Forest seed"]=seed
    scene["Lighting preset"]=look
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(out))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("blend",type=Path)
    p.add_argument("frames",type=Path)
    p.add_argument("--seed",type=int,default=7538)
    p.add_argument("--look",choices=("dawn","blue-hour"),default="dawn")
    args=p.parse_args(sys.argv[sys.argv.index("--")+1:])
    build(args.blend.resolve(),args.frames.resolve(),args.seed,args.look)


if __name__=="__main__":
    main()
