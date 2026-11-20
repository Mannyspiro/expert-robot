"""Independent geometric oracle. Run with the distribution Python and FreeCAD libraries."""
import json
from pathlib import Path
import FreeCAD as App, Part
root=Path(__file__).resolve().parent
p=json.loads((root/'frozen.json').read_text())
def box(coords):
    origin,size=coords
    return Part.makeBox(*size,App.Vector(*origin))
r=box(([0,0,0],p['room']))
rows=[]
for case in p['cases']:
    a,b=(box(case[k]) for k in ('body_a','body_b'))
    za=box(case['zone_a']) if 'zone_a' in case else None
    zb=box(case['zone_b']) if 'zone_b' in case else None
    vals={'a_b_body':a.common(b).Volume}
    if za:
        vals.update(b_in_a_service=za.common(b).Volume,zone_outside_room=za.cut(r).Volume)
    if zb:
        vals.update(a_in_b_service=zb.common(a).Volume,service_intersection=za.common(zb).Volume,zone_b_outside_room=zb.cut(r).Volume)
    rows.append(dict(id=case['id'],measured=vals,frozen_exact=all(abs(vals[k]-v)<1e-9 for k,v in case['expected_volume_m3'].items())))
(root/'freecad.json').write_text(json.dumps(dict(freecad=App.Version()[:3],opencascade=Part.OCC_VERSION,units='m3 (coordinates expressed in metres)',cases=rows),indent=2)+'\n')
