"""Use Blender's Wavefront importer and closed-mesh evaluator. Launch with blender -b."""
from pathlib import Path
import sys,json,bpy,bmesh
root=Path(sys.argv[sys.argv.index('--')+1])
result={}
for asset in sorted(root.glob('*.obj')):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=str(asset),forward_axis='Y',up_axis='Z')
    objects=[]
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH': continue
        bm=bmesh.new()
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        objects.append(dict(key=obj.name,vertices=sorted([list(v.co) for v in bm.verts]),faces=len(bm.faces),watertight=all(e.is_manifold for e in bm.edges), oriented=all(e.is_contiguous for e in bm.edges), signed_volume=bm.calc_volume(signed=True)))
        bm.free()
    result[asset.name]=objects
(root.parent/'blender-result.json').write_text(json.dumps(result,indent=2))
