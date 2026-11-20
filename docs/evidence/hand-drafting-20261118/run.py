from pathlib import Path
import subprocess,json,sys,os,time
root=Path(__file__).resolve().parent
outcomes=[]
for name in ['clean-bend','cross-net','spacing','invalid-endpoint']:
    dest=root/('out-'+name)
    start=time.perf_counter()
    p=subprocess.run([sys.executable,'-m','merlin.science_visualizer','wiring',str(root/(name+'.json')),str(dest)],capture_output=True,text=True)
    outcomes.append(dict(id=name,exit=p.returncode,stderr=p.stderr.strip(),seconds=round(time.perf_counter()-start,4),files=sorted(v.name for v in dest.iterdir()) if dest.is_dir() else []))
(root/'runs.json').write_text(json.dumps(outcomes,indent=2)+'\n')
print(outcomes)
