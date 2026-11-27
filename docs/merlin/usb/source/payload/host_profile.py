"""Discover the CPU and memory capacity available to the Merlin process."""
from hashlib import sha256
import json
import os
from pathlib import Path
import platform


def read(path):
    try:
        return Path(path).read_text()
    except OSError:
        return ""


def count_cpus():
    try:
        affinity=len(os.sched_getaffinity(0))
    except (AttributeError,OSError):
        affinity=os.cpu_count() or 1
    quota_info=read("/sys/fs/cgroup/cpu.max").split()
    if len(quota_info)==2 and all(v.isdigit() for v in quota_info):
        quota,period=map(int,quota_info)
        if quota>0 and period>0: return min(affinity,max(1,quota//period))
    return max(1,affinity)


def detect():
    threads=count_cpus()
    cpu=read("/proc/cpuinfo")
    part=next((line.split(":",1)[1].strip() for line in cpu.splitlines()
                     if line.startswith("model name")),"Linux CPU")
    flags=set(next((line.split(":",1)[1].split() for line in cpu.splitlines()
                     if line.startswith("flags")),[]))
    values={}
    for line in read("/proc/meminfo").splitlines():
        key,_,value=line.partition(":")
        if value.split() and value.split()[0].isdigit(): values[key]=int(value.split()[0])*1024
    memory=values.get("MemTotal",2*1024**3)
    free=values.get("MemAvailable",memory//2)
    cap=read("/sys/fs/cgroup/memory.max").strip()
    use=read("/sys/fs/cgroup/memory.current").strip()
    if cap.isdigit():
        memory=min(memory,int(cap))
        free=min(free,max(0,int(cap)-(int(use) if use.isdigit() else 0)))
    limits=(platform.machine(),part,threads,sorted(flags.intersection({"avx2","f16c","sse2"})),memory//(512*1024**2))
    fingerprint=sha256(json.dumps(limits,separators=(",",":")).encode()).hexdigest()
    return {"machine":platform.machine(),"processor":part,"usable_threads":threads,
       "memory_limit_mib":memory//(1024**2),"available_mib":free//(1024**2),
       "kernel":"AVX2/F16C" if {"avx2","f16c"}<=flags else "scalar",
       "blas_threads":1 if threads<4 or memory<3*1024**3 else 2,
       "initial_threads":min(4,threads),
       "memory_cache_bytes":256*1024 if free<1024**3 else 2*1024**2,
       "fingerprint":fingerprint}
