"""Model the Merlin animation workstation and render workers in Blender."""

import argparse
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def mat(name, rgba, metallic=0):
    material = bpy.data.materials.new(name)
    material.diffuse_color = rgba
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = rgba
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = .33
    return material


def box(name, position, dimensions, material):
    bpy.ops.mesh.primitive_cube_add(size=1, location=position)
    obj = bpy.context.object
    obj.name, obj.dimensions = name, dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bevel = obj.modifiers.new("Machined edges", "BEVEL")
    bevel.width = .055
    bevel.segments = 3
    obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    obj.data.materials.append(material)
    return obj


def light(name, position, color, watts):
    bpy.ops.object.light_add(type="AREA", location=position)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = (-obj.location).to_track_quat("-Z", "Y").to_euler()
    obj.data.energy, obj.data.size, obj.data.color = watts, 7, color


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    opts = parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    out = opts.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    board = mat("Dark violet ceramic", (.072,.031,.115,1), .24)
    vm = mat("Studio VM", (.12,.58,.66,1), .34)
    cpu = mat("Host CPU render workers", (.43,.11,.67,1), .38)
    memory = mat("RAM", (.66,.42,.79,1), .27)
    nvme = mat("NVMe render cache", (.72,.31,.12,1), .48)
    gpu = mat("Optional physical GPU", (.28,.33,.40,1), .48)
    cable = mat("Data paths", (.88,.47,.18,1), .65)
    box("Workstation base", (0,0,0), (11,6,.3), board)
    box("Studio VM", (-3.5,.95,.49), (2.36,2.24,.66), vm)
    box("VM display controller", (-3.5,.95,.91), (1.55,1.39,.2), vm)
    box("Host CPU", (0,.95,.48), (3.32,2.56,.63), cpu)
    for index in range(8):
        box(f"CPU thread {index+1}", (-1.08+.72*(index%4),.46+1.0*(index//4),.89), (.55,.72,.18), memory)
    for index in range(2):
        box(f"RAM bank {index+1}", (-1.28+index*1.25,-1.26,.43), (1.05,.44,.53), memory)
    box("NVMe scratch volume", (0,-2.08,.32), (2.32,.55,.25), nvme)
    box("Optional GPU", (3.58,.89,.46), (2.64,2.04,.58), gpu)
    for index in range(6):
        box(f"GPU heatsink fin {index+1}", (2.60+.39*index,.89,.83), (.22,1.72,.22), gpu)
    for y in (.28,.96,1.63):
        for x in (-1.98,1.98):
            box(f"Board trace {x} {y}", (x,y,.22), (1.05,.065,.1), cable)
    box("Cache connection", (0,-.50,.21), (.095,2.63,.09), cable)
    floor = mat("Studio floor", (.018,.011,.032,1), .13)
    box("Studio floor", (0,0,-.39), (200,200,.35), floor)
    bpy.ops.object.camera_add(location=(10,-15,14))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((0,0,.22))-camera.location).to_track_quat("-Z","Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 13
    scene.camera = camera
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 20
    scene.cycles.device = "CPU"
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    scene.render.resolution_percentage = 75
    scene.render.threads_mode, scene.render.threads = "FIXED", 4
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.world = bpy.data.worlds.new("Violet ambience")
    scene.world.color = (.11,.08,.14)
    light("Lavender key", (-5,0,8), (.75,.62,1), 2600)
    light("Amber rim", (5,5,7), (1,.49,.2), 2300)
    light("Cool fill", (1,-7,5), (.25,.65,1), 1550)
    scene["Scope"] = "Conceptual visualization. Dimensions are scene units rather than PCB dimensions."
    scene.render.filepath = "//Merlin_Render_Workstation.png"
    bpy.ops.wm.save_as_mainfile(filepath=str(out/"Merlin_Render_Workstation.blend"))
    scene.render.filepath = str(out/"Merlin_Render_Workstation.png")
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
