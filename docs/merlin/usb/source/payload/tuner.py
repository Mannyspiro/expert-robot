"""Tune the local simulated chip's thread count using two deterministic test sets."""
import ctypes
from hashlib import sha256
import json
import os
from pathlib import Path
from statistics import median
import sys
from tempfile import NamedTemporaryFile
from time import time,perf_counter

import numpy as np
from host_profile import detect

MAX_AGE=24*3600


def identity(portable):
    return (portable/"runtime-x86_64.sha256").read_text().strip()


def configuration(path,portable,host=None):
    host=host or detect()
    fallback=host["initial_threads"]
    try:
        item=json.loads(path.read_text())
        if (item["runtime"]!=identity(portable) or item.get("host")!=host["fingerprint"]
                or not 1<=item["selected_threads"]<=min(8,host["usable_threads"])):
            return fallback,False
        return item["selected_threads"],0<=time()-item["timestamp"]<MAX_AGE
    except (OSError,ValueError,TypeError,KeyError):
        return fallback,False


def samples(seed, shapes):
    rng=np.random.default_rng(seed)
    for m,n,groups,kind in shapes:
        x=rng.integers(-110,111,size=(m,groups,32),dtype=np.int8)
        s=np.full((m,groups),0.04,dtype=np.float32)
        width=18 if kind==2 else 34
        packed=rng.integers(0,256,size=(n,groups,width),dtype=np.uint8)
        packed[...,:2]=[0,44]  # positive FP16 scale 1/16, little endian
        yield x,s,np.ascontiguousarray(packed),n,kind


def tune(portable,runtime,report,baseline,host=None):
    host=host or detect()
    sys.path.insert(0,str(portable/"simulator"))
    from full_sim import Kernel, fit_layouts
    from usb import kernel_file
    library=kernel_file(runtime,"auto")
    native=ctypes.CDLL(str(library))
    native.set_kernel_threads.argtypes=[ctypes.c_int]
    native.set_kernel_threads.restype=None
    fit=fit_layouts(portable/"simulator/Cell_Results.json")["tetrahedral"]
    kernel=Kernel(library,fit,"corrected")
    cases=(
        tuple(samples(41,[(8,512,24,2),(12,768,18,8),(2,6144,16,2)])),
        tuple(samples(109,[(6,768,28,2),(7,512,33,8),(1,5376,24,2)])),
    )
    ceiling=min(8,host["usable_threads"])
    counts=sorted({baseline,1,*[n for n in (2,4,ceiling) if n<=ceiling]})
    native.set_kernel_threads(baseline)
    expected=[[sha256(kernel.apply(*part).tobytes()).hexdigest() for part in group] for group in cases]
    results=[]
    for threads in counts:
        native.set_kernel_threads(threads)
        valid=True
        timing=[]
        for group,checks in zip(cases,expected,strict=True):
            observed=[]
            for rep in range(4):
                start=perf_counter()
                output=[kernel.apply(*part) for part in group]
                elapsed=perf_counter()-start
                if rep:
                    observed.append(elapsed)
                valid &= [sha256(x.tobytes()).hexdigest() for x in output] == checks
            timing.append(median(observed))
        results.append({"threads":threads,"exact":valid,"median_seconds":timing})
    control=next(x for x in results if x["threads"]==baseline)
    better=[x for x in results if x["exact"] and all(a<=b*.95
            for a,b in zip(x["median_seconds"],control["median_seconds"],strict=True))]
    selected=min(better,key=lambda x:sum(x["median_seconds"]))["threads"] if better else baseline
    receipt={"timestamp":time(),"runtime":identity(portable),"host":host["fingerprint"],"status":"qualified",
             "kernel":library.name,"baseline_threads":baseline,"selected_threads":selected,"candidates":results,
             "rule":"Exact output bytes, at least 5 percent faster on both workloads"}
    report.parent.mkdir(exist_ok=True,parents=True)
    with NamedTemporaryFile(mode="w",dir=report.parent,prefix=".tuner-",delete=False) as out:
        json.dump(receipt,out,indent=2)
        pending=Path(out.name)
    pending.replace(report)
    return receipt
