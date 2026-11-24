#!/usr/bin/env python3
"""Common-input CPU microbenchmark, not a comparison of trained model inference.

Three mathematically distinct reference operators receive identical deterministic
samples. Their outputs solve different tasks, so latency is descriptive only:
no accuracy winner or model-architecture ranking is inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
from statistics import median
import sys
from time import perf_counter

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"python"))
from merlin.simulated_parallax_models import state_recurrence
from merlin.mamba_complex_state_reference import rotating_state
from merlin.parallax_local_linear_reference import local_linear

SIZES=(64,128,256)
REPEATS=5


def compare():
    results=[]
    for n in SIZES:
        rng=random.Random(4500+n)
        signal=[rng.uniform(-1,1) for _ in range(n)]
        xs=list(range(n))
        operators={
            "scalar_recurrence":lambda:state_recurrence(signal,0.8),
            "complex_state_reference":lambda:rotating_state(signal,retention=0.8,angle=0.5),
            "local_linear_reference":lambda:[
                local_linear(xs,signal,float(i),4.0)["estimate"] for i in range(n)],
        }
        variants={}
        for name,fn in operators.items():
            timings=[]
            for _ in range(REPEATS):
                start=perf_counter()
                result=fn()
                timings.append(perf_counter()-start)
                if len(result)!=n:
                    raise AssertionError("operator output shape mismatch")
            variants[name]={"median_seconds":median(timings),
                            "min_seconds":min(timings),
                            "max_seconds":max(timings),
                            "trials":REPEATS,"output_length":n}
        results.append({"n":n,"variants":variants,
                        "input_sha256":hashlib.sha256(
                            json.dumps(signal,separators=(",",":")).encode()).hexdigest()})
    return {"schema":"merlin-common-input-math-reference-benchmark/1",
            "source_commit":os.environ.get("MERLIN_EXPECTED_SHA","unbound"),
            "python_version":platform.python_version(),
            "host_architecture":platform.machine(),
            "sequence_lengths":list(SIZES),"repeats":REPEATS,
            "observations":results,
            "same_input_samples":True,
            "equivalent_prediction_tasks":False,
            "model_inference_executed":False,
            "real_mamba_or_parallax_kernel_executed":False,
            "model_quality_comparable":False,
            "production_qualified":False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    report=compare()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"schema":report["schema"],"sizes":report["sequence_lengths"],
                      "model_inference_executed":False}))


if __name__=="__main__":
    main()
