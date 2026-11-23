#!/usr/bin/env python3
"""Repeatable actual-host timing of a virtual two-channel scalar computation.

A simulated carrier may be useful computation on real CPUs. The benchmark
compares identical synthetic outputs and includes executing the interpreter
but does not measure model quality, GPU kernels, energy or general speedups.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
from statistics import median
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"python"))
from merlin.simulated_parallax_models import run_reference_experiment

SCHEMA="merlin-virtual-substrate-host-benchmark/1"
N_VALUES=(64,128,256,512)
REPEATS=5
SHA=re.compile(r"[0-9a-f]{40}\Z")

def benchmark():
    reported=os.environ.get("MERLIN_EXPECTED_SHA","")
    if reported and not SHA.fullmatch(reported):
        raise ValueError("invalid source SHA admission")
    observations=[]
    for n in N_VALUES:
        trials=[run_reference_experiment(n=n,damping=0.8,window=8,seed=2300+i)
                for i in range(REPEATS)]
        kinds=trials[0]["variants"]
        variants={}
        for kind in kinds:
            times=[t["variants"][kind]["elapsed_seconds"] for t in trials]
            errors=[t["variants"][kind]["max_abs_error_vs_reference"] for t in trials]
            variants[kind]={"latency_median_seconds":median(times),
                            "latency_min_seconds":min(times),
                            "latency_max_seconds":max(times),
                            "max_abs_error":max(errors),
                            "trials":len(times)}
        if variants["scalar_recurrence"]["max_abs_error"] > 1e-10:
            raise ArithmeticError("recurrent numerical reference mismatch")
        observations.append({"n":n,"variants":variants})
    output={
        "schema":SCHEMA,"source_commit":reported or "not_bound_to_version_control",
        "host_python_version":platform.python_version(),
        "host_architecture":platform.machine(),
        "samples_per_size":REPEATS,"sequence_lengths":list(N_VALUES),
        "observations":observations,
        "method":"Python perf_counter around computation calls; synthetic signals; sequential execution; no warmed-up baseline guarantee",
        "real_host_work_measured":True,
        "simulation_virtual_substrate":"discrete recurrent state + truncated local channel",
        "numerical_reference":"direct weighted-history sum",
        "independently_verified_model_quality":False,
        "trained_mamba_or_parallax_executed":False,
        "virtual_device_physical_equivalence_claimed":False,
        "energy_consumption_measured":False,
        "novel_math_proven":False,"production_qualified":False,
    }
    return output

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    result=benchmark()
    body=json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n"
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(body,encoding="utf-8")
    print(json.dumps({"schema":SCHEMA,"sizes":N_VALUES,"samples":REPEATS,
                      "sha256":hashlib.sha256(body.encode()).hexdigest(),
                      "model_gain_verified":False},sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
