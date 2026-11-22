"""Opt-in bounded Merlin self-proposal -> oracle -> QLoRA -> heldout evaluation.

The model proposes only deterministic arithmetic training rows. The QLoRA
controller trains an isolated candidate from a LOCAL trainable Qwen checkpoint
and never mutates GGUF, host services, production weights or authority.
Requires approved local resources and actual supported CUDA hardware.
"""
from __future__ import annotations
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import tempfile
from .agent_practice_runtime import local_endpoint
from .self_edit_data_proposer import (
    proposal_prompt, verify_proposal, write_verified_train_json
)
from .qwen_lora_candidate import _examples, execute


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}",value) is not None


def propose_from_local_model(endpoint,model_id):
    """One bounded loopback model response; no code, network or tools."""
    host,port,route=local_endpoint(endpoint)
    if not isinstance(model_id,str) or re.fullmatch(r"[A-Za-z0-9._/-]{1,100}",model_id) is None:
        raise ValueError("bounded local model alias required")
    request={"model":model_id,
             "messages":[{"role":"user","content":proposal_prompt()}],
             "stream":False,"temperature":0.2,"max_tokens":512}
    con=http.client.HTTPConnection(host,port,timeout=75)
    try:
        con.request("POST",route,
            body=json.dumps(request,sort_keys=True,separators=(",",":")).encode(),
            headers={"Content-Type":"application/json","Connection":"close"})
        reply=con.getresponse()
        if reply.status!=200:
            raise RuntimeError("local model proposal response rejected")
        raw=reply.read(16385)
        if not 0<len(raw)<=16384:
            raise ValueError("model proposal response too large")
        packet=json.loads(raw)
        if type(packet) is not dict or not isinstance(packet.get("choices"),list) or len(packet["choices"])!=1:
            raise ValueError("unexpected model proposal API shape")
        choice=packet["choices"][0]
        message=choice.get("message") if isinstance(choice,dict) else None
        text=message.get("content") if isinstance(message,dict) else None
        if not isinstance(text,str) or not text:
            raise ValueError("model proposal text missing")
        return text
    finally:
        con.close()


def prepare_verified_data(raw_model_proposal,holdout_path,private_scratch):
    heldout=_examples(holdout_path)
    # Private answer labels are never sent to the proposing model.
    checked=verify_proposal(raw_model_proposal,heldout_questions=[
        row["question"] for row in heldout])
    file=Path(private_scratch)/"verified-self-generated-training.json"
    result=write_verified_train_json(checked,file)
    return file, {"schema":checked["schema"],
                  "proposal_sha256":checked["proposal_sha256"],
                  "independent_oracle":checked["independent_oracle"],
                  **result}


def run(*,endpoint,model_id,expected_gguf_sha256,model_dir,
        holdout_path,output_parent,steps=12,rank=4):
    if not _sha(expected_gguf_sha256):
        raise ValueError("operator-supplied full private GGUF digest required")
    if not isinstance(output_parent,Path) or not output_parent.is_dir() or output_parent.is_symlink():
        raise ValueError("preexisting private candidate directory required")
    with tempfile.TemporaryDirectory(prefix="merlin-self-train-proposal-",dir=output_parent) as temp:
        response=propose_from_local_model(endpoint,model_id)
        training_path,training_receipt=prepare_verified_data(
            response,holdout_path,Path(temp))
        result=execute(model_dir,training_path,holdout_path,output_parent,
                       steps=steps,rank=rank)
        return {
            "schema":"merlin-self-training-loop/1",
            "proposal_source":"local_language_model",
            "local_proposer_gguf_sha256_operator_declared":
                expected_gguf_sha256,
            "proposer_identity_not_runtime_attested":True,
            "training_verification":training_receipt,
            "candidate_training":result,
            "trainable_source_checkpoint_independently_verified":False,
            "promotion_authority":False,
            "production_qualified":False}


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--endpoint",required=True)
    parser.add_argument("--model-id",default="local")
    parser.add_argument("--expected-gguf-sha256",required=True)
    parser.add_argument("--trainable-checkpoint-dir",required=True)
    parser.add_argument("--heldout-json",required=True)
    parser.add_argument("--candidate-parent",required=True)
    parser.add_argument("--steps",type=int,default=12)
    parser.add_argument("--rank",type=int,default=4)
    parser.add_argument("--execute",action="store_true",
                        help="explicit local self-proposal and adapter training")
    args=parser.parse_args(argv)
    if not args.execute:
        raise ValueError("no model calls or weight edits without --execute")
    report=run(endpoint=args.endpoint,model_id=args.model_id,
               expected_gguf_sha256=args.expected_gguf_sha256,
               model_dir=Path(args.trainable_checkpoint_dir),
               holdout_path=Path(args.heldout_json),
               output_parent=Path(args.candidate_parent),
               steps=args.steps,rank=args.rank)
    print(json.dumps(report,sort_keys=True,allow_nan=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
