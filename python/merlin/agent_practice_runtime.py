"""Explicit loopback-only in-context practice probe for Merlin's local model.

This is a *test-time evaluation*, not fine-tuning: no model weights, provider,
deployments, network policy, or live secrets are altered. The caller is required
to have started the model separately and authorizes up to 14 local requests.
"""
from __future__ import annotations

import http.client
import json
import re
import time
from urllib.parse import urlsplit
from .agent_training_bench import TASKS, compare_practice_effect, practice_context, validate_bank


class LocalPracticeProbeError(RuntimeError):
    pass


def local_endpoint(value):
    if not isinstance(value,str) or len(value)>200:
        raise ValueError("bounded local model URL required")
    url=urlsplit(value)
    if (url.scheme!="http" or url.hostname not in ("127.0.0.1","localhost")
            or url.username is not None or url.password is not None
            or url.query or url.fragment
            or url.path not in ("", "/v1/chat/completions")):
        raise ValueError("only fixed loopback chat endpoint admitted")
    port=url.port
    if type(port) is not int or not 1<=port<=65535:
        raise ValueError("explicit bounded localhost port required")
    return "127.0.0.1",port,"/v1/chat/completions"


def request_local_model(endpoint,model_id,prompt,*,timeout_seconds=75):
    host,port,path=local_endpoint(endpoint)
    if (not isinstance(model_id,str) or not re.fullmatch(r"[A-Za-z0-9._/-]{1,100}",model_id)
            or not isinstance(prompt,str) or not 0<len(prompt)<=4096
            or type(timeout_seconds) is not int or not 1<=timeout_seconds<=120):
        raise ValueError("bounded inference request fields required")
    request={"model":model_id,"messages":[{"role":"user","content":prompt}],
             "stream":False,"temperature":0.0,"max_tokens":64}
    channel=http.client.HTTPConnection(host,port,timeout=timeout_seconds)
    try:
        body=json.dumps(request,allow_nan=False,separators=(",",":")).encode()
        channel.request("POST",path,body=body,
                        headers={"Content-Type":"application/json","Connection":"close"})
        reply=channel.getresponse()
        if reply.status!=200:
            raise LocalPracticeProbeError("local model returned non-success HTTP")
        raw=reply.read(32769)
        if not 0<len(raw)<=32768:
            raise LocalPracticeProbeError("local model output outside byte budget")
        response=json.loads(raw)
        if not isinstance(response,dict):
            raise LocalPracticeProbeError("model response was not JSON object")
        choices=response.get("choices")
        if not isinstance(choices,list) or len(choices)!=1 or not isinstance(choices[0],dict):
            raise LocalPracticeProbeError("model response did not include one choice")
        message=choices[0].get("message")
        answer=message.get("content") if isinstance(message,dict) else None
        if not isinstance(answer,str) or not 0<len(answer)<=4096:
            raise LocalPracticeProbeError("model answer malformed")
        return answer
    finally:
        channel.close()


def paired_probe(transport,*,model_identity,task_bank=TASKS,max_seconds=900):
    """Compare blind heldout questions before/after in-context demonstrations.

    The caller supplies a trusted transport callable; it must invoke the SAME
    pinned model at both phases. This function does not attest to that identity.
    """
    validate_bank(task_bank)
    if not callable(transport):
        raise ValueError("callable local model transport required")
    if not isinstance(model_identity,str) or not re.fullmatch(r"[a-zA-Z0-9:._/-]{1,200}",model_identity):
        raise ValueError("explicit pinned model identity required")
    if type(max_seconds) is not int or not 1<=max_seconds<=3600:
        raise ValueError("bounded evaluation time budget required")
    holdout=sorted((task for task in task_bank if task.split=="holdout"),
                   key=lambda item:item.task_id)
    if len(holdout)>32:
        raise ValueError("too many heldout tasks for bounded probe")
    deadline=time.monotonic()+max_seconds
    baseline={}
    practiced={}
    # Alternate rounds to reduce bias from phase-specific model load or drift.
    for task in holdout:
        if time.monotonic()>=deadline:
            raise LocalPracticeProbeError("heldout probe time budget exhausted")
        raw=transport(task.question)
        if not isinstance(raw,str) or not 0<len(raw)<=4096:
            raise LocalPracticeProbeError("invalid baseline answer")
        baseline[task.task_id]=raw
        if time.monotonic()>=deadline:
            raise LocalPracticeProbeError("heldout probe time budget exhausted")
        guided=transport(practice_context(task.domain,task_id=task.task_id,
                                          tasks=task_bank))
        if not isinstance(guided,str) or not 0<len(guided)<=4096:
            raise LocalPracticeProbeError("invalid guided answer")
        practiced[task.task_id]=guided
    outcome=compare_practice_effect(baseline,practiced,tasks=task_bank)
    outcome["model_identity_supplied_not_attested"]=model_identity
    outcome["model_calls_observed"]=2*len(holdout)
    outcome["probe_mode"]="in_context_only"
    outcome["source_of_answers"]="caller_transport"
    outcome["model_weights_updated"]=False
    outcome["model_quality_qualified"]=False
    return outcome


__all__=["local_endpoint","request_local_model","paired_probe","LocalPracticeProbeError"]
