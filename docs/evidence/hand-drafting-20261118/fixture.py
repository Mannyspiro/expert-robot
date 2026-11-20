import json,copy
from pathlib import Path
base=Path(__file__).resolve().parent
p=json.loads((base/'frozen.json').read_text())
def emit(name,paths):
 components=[];nets=[]
 for index,path in enumerate(paths):
  start,end=path[0],path[-1]
  s,t=f'S{index}',f'T{index}'
  for ident,(x,y) in [(s,start),(t,end)]:
   components.append(dict(id=ident,origin=[x-1,y-1],size=[1,1],pins=[dict(id='signal',offset=[1,1])]))
  nets.append(dict(id=f'N{index}',routes=[{'from':f'{s}.signal','to':f'{t}.signal','points':path}]))
 data=dict(title='Synthetic spectroscopy wiring',unit='mm',components=components,nets=nets)
 (base/(name+'.json')).write_text(json.dumps(data,indent=2)+'\n')
 return data
for case in p['probes'][:3]:
 emit(case['id'],case['paths'])
bad=json.loads((base/'clean-bend.json').read_text())
bad['nets'][0]['routes'][0]['to']='unknown.signal'
(base/'invalid-endpoint.json').write_text(json.dumps(bad,indent=2)+'\n')
