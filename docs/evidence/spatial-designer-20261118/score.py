from pathlib import Path
import itertools,json,hashlib,sys,datetime,math
from merlin.scientific_loop import Observation,Prediction,compare_observation
import merlin.scientific_loop as scientific_loop
p=Path(__file__).resolve().parent
def read(path):return json.loads((p/path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
cfg=read('valid.json')
exp=read('frozen.json')
blender=read('blender-result.json')
report=read('out/critique.json')
assessed=[]
for src in cfg['layouts']:
 name=src['name']
 match=next(r for r in report['layouts'] if r['name']==name)
 pred=exp['expected'][name]
 collisions=match['collisions']
 clash_ok=({tuple(sorted(pair)) for pair in collisions}==({('display','spectrometer')} if pred['clash'] else set()))
 bounds_ok=(set(match['out_of_bounds'])==({'display'} if pred['outside'] else set()))
 models=[fn for fn in blender if fn in str(match)]
 assert len(models)==1,match
 objects=blender[models[0]]
 checks=[]
 for item in src['items']:
  expected=sorted(tuple(a+b for a,b in zip(item['origin'],off)) for off in itertools.product(*[(0,s) for s in item['size']]))
  hits=[o for o in objects if sorted(map(tuple,o['vertices']))==expected]
  checks.append(bool(len(hits)==1 and hits[0]['faces'] in (6,12) and hits[0]['oriented'] and hits[0]['watertight'] and math.isclose(hits[0]['signed_volume'],math.prod(item['size']),abs_tol=1e-6)))
 assessed.append(dict(name=name,exact_clash=clash_ok,exact_bounds=bounds_ok,meshes=checks,mesh_count=len(objects)))
result=dict(cases=assessed,blender_version='4.3.2',protocol_sha256=sha(p/'frozen.json'),input_sha256=sha(p/'valid.json'),invalid_input_rejected=read('invalid-result.json'),scope=exp['scope'])
observations=dict(correct_critiques=sum(c['exact_clash'] and c['exact_bounds'] for c in assessed),exact_meshes=sum(sum(c['meshes']) for c in assessed),rejects=int(result['invalid_input_rejected']['exit_code']!=0 and not result['invalid_input_rejected']['output_exists']))
limits=dict(correct_critiques=5,exact_meshes=10,rejects=1)
raw=json.dumps(result,sort_keys=True).encode()
obs=Observation('synthetic-exhibit-layout-heldout','Are exported solids faithful and are frozen critiques correct?',"Merlin CLI, frozen synthetic coordinates, and independent Blender OBJ importer",observations,{k:'cases' for k in limits},{k:0 for k in limits},{'scope':exp['scope']},(result['protocol_sha256'],result['input_sha256']),datetime.datetime.now(datetime.timezone.utc).isoformat(),hashlib.sha256(raw).hexdigest())
result.update(scientific_loop_source_sha256=sha(scientific_loop.__file__),assessment=compare_observation(obs,[Prediction(k,n,0,'cases') for k,n in limits.items()]))
(p/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['assessment'])
