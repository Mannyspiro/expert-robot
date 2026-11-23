#!/usr/bin/env python3
"""CPU-capable, source-pinned Qwen 0.5B LoRA run with disjoint baseline/adaptor eval.
Never reads user conversations, CI secrets, private files or pushes model weights.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import sys
import time
import traceback
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import LoraConfig, get_peft_model

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/"config/merlin/model-training/capability_v1.json"
PROMPT_SYSTEM=(
    "You are Merlin, a local offline assistant. When reading workspace files, "
    "respond with only a JSON object having exactly 'name' and 'arguments'. "
    "Available read-only tools are read_file and list_files, with a path argument. "
    "Never invent executed tool results. If the user did not ask for a file listing "
    "or read, answer succinctly in plain text. Never delete, run commands, or send "
    "workspace data using read-only tool calls."
)

def dump(path, obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,sort_keys=True,ensure_ascii=False)+"\n")

def byteshash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def validate_dataset(data):
    assert data["schema"]=="merlin-capability-training/1"
    tr=data["train"]; te=data["holdout"]
    assert len(tr)>=20 and len(te)>=10
    assert len({x["id"] for x in tr+te})==len(tr)+len(te)
    assert not ({x["prompt"] for x in tr}&{x["prompt"] for x in te})
    for item in tr+te:
        assert item["kind"] in ("tool","answer","no_tool")
        assert isinstance(item["prompt"],str) and 1<=len(item["prompt"])<=256
        if item["kind"]=="tool":
            assert set(item["expected"])=={"name","arguments"}
            assert item["expected"]["name"] in ("read_file","list_files")
            assert set(item["expected"]["arguments"])=={"path"}
    return tr,te

def expected_output(row):
    obj=row.get("expected")
    if row["kind"]=="tool":
        return json.dumps(obj,separators=(",",":"),ensure_ascii=False)
    if row["kind"]=="no_tool":
        return "I cannot perform that action with these read-only tools."
    return obj

def render(tokenizer,prompt):
    return tokenizer.apply_chat_template(
        [{"role":"system","content":PROMPT_SYSTEM},{"role":"user","content":prompt}],
        tokenize=False,add_generation_prompt=True
    )

def predict(model, tokenizer, prompt, tokens=64):
    model.eval()
    raw=render(tokenizer,prompt)
    enc=tokenizer(raw,return_tensors="pt",add_special_tokens=False)
    with torch.inference_mode():
        out=model.generate(**enc, max_new_tokens=tokens,do_sample=False,
                           pad_token_id=tokenizer.eos_token_id)
    return tokenizer.decode(out[0][enc["input_ids"].shape[1]:],
                            skip_special_tokens=True).strip()

def normalize(text):
    return re.sub(r"[^a-z0-9]+","",text.lower())

def score(row, output):
    if row["kind"]=="tool":
        try:
            obj=json.loads(output)
        except (ValueError,TypeError):
            return False
        return obj==row["expected"]
    if row["kind"]=="no_tool":
        return no_tool_score(output)
    return normalize(output)==normalize(str(row["expected"]))

def no_tool_score(output):
    try:
        obj=json.loads(output)
        if isinstance(obj,dict) and ("name" in obj or "arguments" in obj):
            return False
    except (ValueError,TypeError):
        pass
    return bool(output.strip())

def eval_split(model,tok,split, label, limit=64):
    results=[]
    for i,item in enumerate(split):
        start=time.monotonic()
        try:
            output=predict(model,tok,item["prompt"],limit)
            correct=no_tool_score(output) if item["kind"]=="no_tool" else score(item,output)
            results.append({"id":item["id"],"kind":item["kind"],"expected":item.get("expected"),
                            "reply":output[:512],"pass":bool(correct),
                            "elapsed_seconds":round(time.monotonic()-start,3)})
        except Exception as exc:
            results.append({"id":item["id"],"kind":item["kind"],"pass":False,
                            "error":str(exc)[:250]})
        print(label,item["id"],results[-1]["pass"],flush=True)
    return results

def metrics(rows):
    from collections import defaultdict
    groups=defaultdict(list)
    for r in rows:
        groups[r["kind"]].append(bool(r["pass"]))
    return {
        "total":len(rows),"passed":sum(x["pass"] for x in rows),
        "accuracy":sum(x["pass"] for x in rows)/max(1,len(rows)),
        "by_kind":{k:{"correct":sum(v),"total":len(v)} for k,v in sorted(groups.items())}
    }

def train_lora(model,tok,train,steps_cap, output):
    from peft import LoraConfig, get_peft_model
    model.config.use_cache=False
    model.gradient_checkpointing_enable()
    config=LoraConfig(r=4,lora_alpha=8,lora_dropout=0.0,
                      target_modules=["q_proj","v_proj"],bias="none",task_type="CAUSAL_LM")
    model=get_peft_model(model,config)
    model.train()
    parameters=[p for p in model.parameters() if p.requires_grad]
    print("TRAINABLE",sum(p.numel() for p in parameters),flush=True)
    optimizer=torch.optim.AdamW(parameters,lr=1e-4,weight_decay=0.0)
    losses=[]
    for i,row in enumerate(train[:steps_cap]):
        prefix=render(tok,row["prompt"])
        answer=expected_output(row)+tok.eos_token
        a=tok(prefix,add_special_tokens=False)["input_ids"]
        b=tok(answer,add_special_tokens=False)["input_ids"]
        if len(a)+len(b)>320:
            raise ValueError("Training example exceeds bounded token window")
        ids=torch.tensor([a+b],dtype=torch.long)
        labels=torch.tensor([[-100]*len(a)+b],dtype=torch.long)
        optimizer.zero_grad(set_to_none=True)
        result=model(input_ids=ids,labels=labels)
        loss=result.loss
        if not torch.isfinite(loss).item():
            raise FloatingPointError("Non-finite training loss")
        loss.backward()
        optimizer.step()
        losses.append(round(float(loss.detach()),5))
        print(f"TRAIN step={i+1} loss={losses[-1]}",flush=True)
    model.save_pretrained(output,safe_serialization=True)
    return model, losses

def acquire_pinned_model(model_id, revision, report, evidence_path):
    """Download a complete pinned safetensors snapshot; distinguish network failure from model failure."""
    from huggingface_hub import snapshot_download
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "180")
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "40")
    last_error = None
    for attempt in range(1, 4):
        try:
            snapshot = Path(snapshot_download(
                repo_id=model_id,
                revision=revision,
                allow_patterns=["*.safetensors", "*.json", "*.txt", "*.model",
                                "*.tiktoken", "*.bpe", "*.vocab", "*.merges"],
                token=False, max_workers=2
            ))
            weights = sorted(snapshot.glob("*.safetensors"))
            if not weights:
                raise FileNotFoundError("Pinned model snapshot contains no safetensors")
            manifests = [{
                "name": p.name, "size_bytes": p.stat().st_size,
                "sha256": byteshash(p)
            } for p in weights]
            report["pinned_checkpoint_files"] = manifests
            report["model_download_status"] = "complete_verified_safetensors"
            dump(evidence_path, report)
            return snapshot
        except (OSError, RuntimeError, ValueError) as exc:
            last_error = type(exc).__name__ + ": " + str(exc)[:400]
            print(f"MODEL_DOWNLOAD attempt={attempt}/3 failure={type(exc).__name__}", flush=True)
            report["model_download_status"] = "retrying" if attempt < 3 else "failed"
            report["model_download_attempts"] = attempt
            report["last_download_error"] = last_error
            dump(evidence_path, report)
            if attempt < 3:
                time.sleep(5 * attempt)
    raise RuntimeError("Pinned model retrieval failed after three bounded attempts: " + str(last_error))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    parser.add_argument("--steps",type=int,default=24)
    parser.add_argument("--skip-training",action="store_true")
    args=parser.parse_args()
    assert 1<=args.steps<=29
    output=Path(args.output).resolve()
    assert not output.exists()
    output.mkdir(parents=True)
    raw=DATA.read_bytes();data=json.loads(raw)
    training,holdout=validate_dataset(data)
    torch.set_num_threads(min(4,os.cpu_count() or 2))
    torch.manual_seed(1701);random.seed(1701)
    model_id=data["model"]["id"];revision=data["model"]["revision"]
    report={"schema":"merlin-local-model-training-report/1",
        "model_id":model_id,"revision":revision,"dataset_sha256":hashlib.sha256(raw).hexdigest(),
        "training_method":"PEFT LoRA r=4, supervised assistant completion only",
        "training_examples_available":len(training),"heldout_examples":len(holdout),
        "steps_requested":args.steps,"weights_created":False,"results":{},
        "production_qualified":False,"apk_packaging_permitted":False}
    dump(output/"report.json",report)
    try:
        snapshot=acquire_pinned_model(model_id,revision,report,output/"report.json")
        tok=AutoTokenizer.from_pretrained(str(snapshot),local_files_only=True,trust_remote_code=False)
        model=AutoModelForCausalLM.from_pretrained(
            str(snapshot),local_files_only=True,torch_dtype=torch.float32,
            trust_remote_code=False,attn_implementation="eager",low_cpu_mem_usage=True)
        print("BASELINE HOLDOUT",flush=True)
        base=eval_split(model,tok,holdout,"baseline")
        report["results"]["baseline"]={"metrics":metrics(base),"cases":base}
        dump(output/"report.json",report)
        if not args.skip_training:
            print("TRAINING ACTUAL MODEL WEIGHTS",flush=True)
            model,losses=train_lora(model,tok,training,args.steps,output/"adapter")
            report["results"]["training_losses"]=losses
            report["weights_created"]=True
            dump(output/"report.json",report)
            trained=eval_split(model,tok,holdout,"trained")
            report["results"]["trained"]={"metrics":metrics(trained),"cases":trained}
            baseline=report["results"]["baseline"]["metrics"]
            candidate=report["results"]["trained"]["metrics"]
            report["results"]["deltas"]={
                "correct":candidate["passed"]-baseline["passed"],
                "tool_correct":candidate["by_kind"].get("tool",{}).get("correct",0)-
                               baseline["by_kind"].get("tool",{}).get("correct",0)}
            # With few holdouts, an improvement is exploratory, not a production qualifier.
            report["model_capability_gate_passed"]=(
                candidate["passed"]>baseline["passed"] and
                candidate["by_kind"].get("tool",{}).get("correct",0)>
                baseline["by_kind"].get("tool",{}).get("correct",0) and
                candidate["by_kind"].get("answer",{}).get("correct",0)>=
                baseline["by_kind"].get("answer",{}).get("correct",0) and
                candidate["by_kind"].get("no_tool",{}).get("correct",0)>=
                baseline["by_kind"].get("no_tool",{}).get("correct",0))
        report["status"]="completed"
        dump(output/"report.json",report)
        print(json.dumps({k:v for k,v in report.items() if k!="results"},sort_keys=True),flush=True)
    except BaseException as e:
        report["status"]="failed"
        report["error"]=type(e).__name__+": "+str(e)[:500]
        dump(output/"report.json",report)
        raise

if __name__=="__main__":
    main()
