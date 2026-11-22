"""A Merlin language-model-authored proposal may edit a tiny detached tensor.

The real model can propose a JSON rank-one weight edit; an independent verifier
applies it and tests an untouched heldout sample. Only the toy tensor is
eligible; production language-model tensors, checkpoints and deployed weights
are never eligible. The caller's local model adapter may be called at most once.
"""
from __future__ import annotations

import json
from .self_rewrite_lab import (
    PROPOSAL_SCHEMA, digest, matrix, validate_proposal, gate,
)
from .agent_practice_runtime import request_local_model


def proposal_prompt(weights, practice):
    w=matrix(weights)
    if len(w)!=len(w[0]) or len(w)>8:
        raise ValueError("model-proposed toy edit must use <=8 square channels")
    if not isinstance(practice,(tuple,list)) or not 1<=len(practice)<=8:
        raise ValueError("bounded public practice examples required")
    for pair in practice:
        if (not isinstance(pair,(tuple,list)) or len(pair)!=2
                or len(pair[0])!=len(w[0]) or len(pair[1])!=len(w)):
            raise ValueError("practice tensor shape differs")
    training=[{"input":list(x),"expected_output":list(y)} for x,y in practice]
    instructions={
        "task":"Propose ONE bounded gradient-free numeric edit to the detached synthetic output tensor. Reply with ONLY one JSON object, no markdown, no code.",
        "allowed_schema":PROPOSAL_SCHEMA,
        "required_fields":["schema","target","weight_sha256","direction","fraction"],
        "target":"synthetic.output",
        "weight_sha256":digest(w),
        "weights":w,
        "public_practice":training,
        "edit_math":"W_new = W_old - fraction*u*(u^T*W_old)",
        "constraints":["direction has same length as output channels and Euclidean norm 1",
                       "0 < fraction <= 0.5","do not write code or request tools"],
        "evaluation":"A separate evaluator tests previously unseen examples, not included here."
    }
    prompt=json.dumps(instructions,sort_keys=True,separators=(",",":"))
    if len(prompt)>4096:
        raise ValueError("bounded local model prompt required")
    return prompt


def evaluate_proposal(model_text, weights, practice, heldout):
    if not isinstance(model_text,str) or len(model_text.encode("utf-8"))>4096:
        raise ValueError("bounded model proposal response required")
    try:
        proposal=json.loads(model_text)
    except (json.JSONDecodeError,UnicodeError) as exc:
        raise ValueError("malformed model proposal JSON") from exc
    base=matrix(weights)
    changed=validate_proposal(proposal,base)
    decision=gate(base,changed,practice,heldout)
    return {"schema":"merlin-llm-proposed-tensor-edit/1",
            "candidate_weights":changed,
            "proposal_sha256":digest(proposal),
            "baseline_weight_sha256":digest(base),
            "candidate_weight_sha256":digest(changed),
            "candidate_is_detached":True,
            "language_model_proposal_received":True,
            "model_generated_proposal_valid":True,
            "actual_numeric_weights_changed":changed!=base,
            "candidate_accepted_for_research":decision["accepted_as_research_candidate"],
            "gate":decision,
            "merlin_gguf_weights_changed":False,
            "candidate_auto_promoted":False,
            "production_qualified":False}


def run_local_once(endpoint, model_id, weights, practice, heldout):
    """Explicit caller-invoked 1-request model proposal; no network/tools."""
    message=proposal_prompt(weights,practice)
    response=request_local_model(endpoint,model_id,message,timeout_seconds=75)
    return evaluate_proposal(response,weights,practice,heldout)


__all__=["proposal_prompt","evaluate_proposal","run_local_once"]
