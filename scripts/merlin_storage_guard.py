#!/usr/bin/env python3
"""Preflight storage guard for bounded Merlin ingestion; never prunes canonical data."""
import argparse, json, shutil
from pathlib import Path

def measure(root):
    total=0; count=0
    for p in root.rglob("*"):
        if p.is_file(): total+=p.stat().st_size; count+=1
    return total,count

def check(root, max_bytes, max_files, reserve_bytes):
    root.mkdir(parents=True,exist_ok=True)
    used,count=measure(root)
    free=shutil.disk_usage(root).free
    errors=[]
    if used>=max_bytes: errors.append("staging byte quota reached")
    if count>=max_files: errors.append("staging record/file quota reached")
    if free<=reserve_bytes: errors.append("free disk reserve reached; ingestion must stop")
    return {"ok":not errors,"staging_bytes":used,"staging_files":count,"free_disk_bytes":free,
            "max_staging_bytes":max_bytes,"max_staging_files":max_files,"free_disk_reserve_bytes":reserve_bytes,
            "errors":errors,"pruning":"disabled; only separately designated rebuildable caches may be pruned"}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--root",type=Path,required=True)
    p.add_argument("--max-bytes",type=int,default=268435456); p.add_argument("--max-files",type=int,default=5000)
    p.add_argument("--reserve-bytes",type=int,default=1073741824); a=p.parse_args()
    r=check(a.root,a.max_bytes,a.max_files,a.reserve_bytes); print(json.dumps(r,indent=2))
    return 0 if r["ok"] else 3
if __name__=="__main__": raise SystemExit(main())
