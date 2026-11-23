#!/usr/bin/env python3
"""Independent real local-model inference acceptance, never a mock.

Requires an operator-supplied running loopback model server and loaded weights.
An endpoint's model list alone is insufficient: generate a fresh response.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
from time import monotonic

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"portable"/"merlin_studio"))
from model import LocalModel, endpoint_parts


def validate(endpoint:str, model_id:str, *, timeout:int=45)->dict:
    if endpoint_parts(endpoint) is None:
        raise ValueError("explicit loopback endpoint required")
    if not isinstance(model_id,str) or not 1<=len(model_id)<=200:
        raise ValueError("explicit bounded model identifier required")
    if type(timeout) is not int or not 10<=timeout<=120:
        raise ValueError("bounded inference timeout required")
    settings={"model_url":endpoint,"model_id":model_id,
              "model_timeout_seconds":timeout,"max_output_tokens":128,
              "tool_compatibility":"native"}
    model=LocalModel(settings)
    if model.transport is not None:
        raise AssertionError("injected transport is not independent inference")
    probe=model.probe()
    if not probe["reachable"] or model_id not in [x["id"] for x in probe["models"]]:
        raise RuntimeError("specified real local model not advertised by server")
    nonce=secrets.token_hex(8)
    prompt="Respond with exactly the word READY followed by one space and this token: "+nonce
    start=monotonic()
    response=model.complete([{"role":"user","content":prompt}],[],timeout=timeout)
    elapsed=monotonic()-start
    answer=response["content"]
    if not isinstance(answer,str) or not answer.strip():
        raise RuntimeError("real local inference returned empty content")
    return {"schema":"merlin-real-loopback-inference-acceptance/1",
            "model_id":model_id,"endpoint_is_loopback":True,
            "model_list_verified":True,"generation_request_completed":True,
            "challenge_token_echoed":nonce in answer,
            "output_sha256":hashlib.sha256(answer.encode()).hexdigest(),
            "output_length":len(answer),"latency_seconds":elapsed,
            "mock_transport_used":False,"actual_model_weights_verified_independently":False,
            "model_quality_qualified":False,"production_qualified":False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint",required=True)
    parser.add_argument("--model-id",required=True)
    parser.add_argument("--timeout",type=int,default=45)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    report=validate(args.endpoint,args.model_id,timeout=args.timeout)
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("refusing to overwrite previous inference evidence")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":"generated","challenge_token_echoed":report["challenge_token_echoed"],
                      "mock_transport_used":False,"output_sha256":report["output_sha256"]}))
    if not report["challenge_token_echoed"]:
        raise SystemExit("real generation succeeded but challenge fidelity failed")


if __name__=="__main__":
    main()
