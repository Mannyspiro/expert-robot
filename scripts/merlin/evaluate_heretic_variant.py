#!/usr/bin/env python3
"""Hold-out A/B evaluation of real Heretic weights; do not qualify release."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT=Path(__file__).resolve().parents[2]
source=ROOT/"scripts/merlin/train_local_capability.py"
spec=importlib.util.spec_from_file_location("merlin_training_reference",source)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--modified-model",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    dataset=json.loads(m.DATA.read_text())
    _,holdout=m.validate_dataset(dataset)
    original=dataset["model"]["id"]
    revision=dataset["model"]["revision"]
    torch.set_num_threads(min(4,os.cpu_count() or 2))
    tokenizer=AutoTokenizer.from_pretrained(original,revision=revision,trust_remote_code=False)
    model=AutoModelForCausalLM.from_pretrained(
        original,revision=revision,torch_dtype=torch.float32,trust_remote_code=False,
        attn_implementation="eager",low_cpu_mem_usage=True)
    baseline=m.eval_split(model,tokenizer,holdout,"heretic-baseline")
    del model
    model=AutoModelForCausalLM.from_pretrained(
        args.modified_model,torch_dtype=torch.float32,trust_remote_code=False,
        attn_implementation="eager",low_cpu_mem_usage=True)
    variant=m.eval_split(model,tokenizer,holdout,"heretic-modified")
    b=m.metrics(baseline);v=m.metrics(variant)
    base_tool=b["by_kind"].get("tool",{}).get("correct",0)
    variant_tool=v["by_kind"].get("tool",{}).get("correct",0)
    report={
        "schema":"merlin-heretic-capability-ab/1",
        "source_checkpoint":original,
        "source_revision":revision,
        "heretic_source_sha":"aecd4a845a23be3f96ddc03b37b53a9195ee2566",
        "dataset_sha256":m.byteshash(m.DATA),
        "method":"two actual model variants on exactly the same heldout questions",
        "baseline":{"metrics":b,"cases":baseline},
        "modified":{"metrics":v,"cases":variant},
        "tool_delta":variant_tool-base_tool,
        "total_delta":v["passed"]-b["passed"],
        "observed_nonregression":all(
            v["by_kind"].get(kind,{}).get("correct",0)>=b["by_kind"].get(kind,{}).get("correct",0)
            for kind in ("tool","answer","no_tool")),
        "packaging_approved":False,
        "production_qualified":False,
        "not_verified":["Android ABI","real tool execution","user data isolation on device","latency","independent full-domain benchmark","rights review"]
    }
    m.dump(Path(args.output),report)
    print(json.dumps({k:v for k,v in report.items() if k not in ("baseline","modified")},sort_keys=True))
if __name__=="__main__":
    main()
