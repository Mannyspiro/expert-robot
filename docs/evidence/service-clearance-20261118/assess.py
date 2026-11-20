"""Compare the emitted critique against the independent FreeCAD oracle and frozen hypotheses."""
import json,hashlib,datetime
from pathlib import Path
import merlin.scientific_loop as loop
root=Path(__file__).resolve().parent
load=lambda f:json.loads((root/f).read_text())
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
p,fc,rep=map(load,['frozen.json','freecad.json','out/critique.json'])
old=load('legacy-baseline/critique.json')['layouts'][0]
legacy=next(c for c in rep['layouts'] if c['name']=='legacy')
old_obj=sha(root/'legacy-baseline'/old['obj'])
new_obj=sha(root/'out'/legacy['obj'])
legacy_ok=all(old[k]==legacy[k] for k in ('name','collisions','out_of_bounds','items')) and old_obj==new_obj
results=[]
assert sha(root/'frozen.json')=='34a0a7a6f9502d879eef84b79f3cb504cb1af88fdafb260e45ee4025db3a7c6f'
assert [c['id'] for c in p['cases']]==[c['id'] for c in fc['cases']]==[c['name'] for c in rep['layouts']]
for case,vol,row in zip(p['cases'],fc['cases'],rep['layouts']):
    v=vol['measured']
    keys=['service_intrusions','service_out_of_bounds','simultaneous_service_conflicts','service_zones']
    expected={k:[] for k in keys}
    for suffix,owner in [('a','spectrometer'),('b','microscope')]:
        if 'zone_'+suffix in case:
            origin,size=case['zone_'+suffix]
            expected['service_zones'].append(dict(owner=owner,id='calibration',origin=origin,size=size))
    for vkey,owner,other in [('b_in_a_service','spectrometer','microscope'),('a_in_b_service','microscope','spectrometer')]:
        if v.get(vkey,0)>1e-9: expected['service_intrusions'].append(dict(owner=owner,zone='calibration',equipment=other))
    for vkey,owner in [('zone_outside_room','spectrometer'),('zone_b_outside_room','microscope')]:
        if v.get(vkey,0)>1e-9: expected['service_out_of_bounds'].append(dict(owner=owner,zone='calibration'))
    if v.get('service_intersection',0)>1e-9:
        expected['simultaneous_service_conflicts'].append(dict(owner_a='spectrometer',zone_a='calibration',owner_b='microscope',zone_b='calibration'))
    def normalize_conflicts(items):
        return sorted(sorted([(r['owner_a'],r['zone_a']),(r['owner_b'],r['zone_b'])]) for r in items)
    correct={}
    for k in keys:
        if k=='simultaneous_service_conflicts': correct[k]=normalize_conflicts(expected[k])==normalize_conflicts(row[k])
        else: correct[k]=sorted(expected[k],key=lambda i:i['owner'])==sorted(row[k],key=lambda i:i['owner'])
    correct['equipment']=row['collisions']==[] and row['out_of_bounds']==[]
    results.append(dict(id=case['id'],cad_matches_expected=vol['frozen_exact'],labels=correct))
facts=dict(geometry_oracles=sum(c['cad_matches_expected'] for c in results),exact_reports=sum(all(c['labels'].values()) for c in results),legacy_compatibility=int(legacy_ok))
pred=dict(geometry_oracles=6,exact_reports=6,legacy_compatibility=1)
receipt=dict(protocol_sha256=sha(root/'frozen.json'),input_sha256=sha(root/'fixture.json'),critique_sha256=sha(root/'out/critique.json'),freecad_sha256=sha(root/'freecad.json'),normal_entry='python -m merlin.science_visualizer layout INPUT OUTDIR',source_scientific_loop_sha256=sha(loop.__file__),old_obj_sha256=old_obj,new_obj_sha256=new_obj,cases=results,observed=facts,freecad='.'.join(fc['freecad']),opencascade=fc['opencascade'])
obs=loop.Observation('maintenance-clearance-holdout','Does Merlin identify positive-volume equipment/service conflicts on the six frozen lab layouts?', 'Independent FreeCAD solid booleans and observed CLI report',facts,{k:'cases' for k in pred},{k:0 for k in pred},{'scope':'Synthetic axis-aligned lab boxes only, metres; CAD absolute tolerance 1e-9 m3; no engineering certification.'},(receipt['protocol_sha256'],receipt['freecad_sha256'],receipt['critique_sha256']),datetime.datetime.now(datetime.timezone.utc).isoformat(),receipt['critique_sha256'])
receipt['assessment']=loop.compare_observation(obs,[loop.Prediction(k,v,0,'cases') for k,v in pred.items()])
(root/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(receipt['assessment'])
