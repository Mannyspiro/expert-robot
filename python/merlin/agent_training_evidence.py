"""Persist bounded nonsecret Merlin practice-evaluation receipts canonically.

No raw prompts/responses, credentials or model weights are written. A registry
artifact is NOT evidence that an independent model evaluation actually ran.
"""
from __future__ import annotations
from hashlib import sha256
import json
import re


ALLOWED_FIELDS = frozenset({
    "schema","task_bank_sha256","heldout_count","baseline_correct",
    "after_practice_correct","delta_correct","improved_case_ids",
    "regressed_case_ids","model_weights_updated","mastery_qualified",
    "not_established","model_identity_supplied_not_attested",
    "model_calls_observed","probe_mode","source_of_answers",
    "model_quality_qualified",
})


def canonical_receipt(receipt):
    if (type(receipt) is not dict
            or set(receipt)-ALLOWED_FIELDS
            or receipt.get("schema")!="merlin-paired-practice-effect/1"
            or receipt.get("model_weights_updated") is not False
            or receipt.get("mastery_qualified") is not False
            or receipt.get("model_quality_qualified") is not False):
        raise ValueError("unqualified exact paired-practice receipt required")
    for name in ("heldout_count","baseline_correct","after_practice_correct",
                 "delta_correct","model_calls_observed"):
        value=receipt.get(name)
        if type(value) is not int or abs(value)>128:
            raise ValueError("invalid bounded evaluation counter")
    count=receipt["heldout_count"]
    if (not 1<=count<=32 or receipt["model_calls_observed"]!=2*count
            or not 0<=receipt["baseline_correct"]<=count
            or not 0<=receipt["after_practice_correct"]<=count
            or receipt["delta_correct"]!=
               receipt["after_practice_correct"]-receipt["baseline_correct"]):
        raise ValueError("inconsistent paired evaluation counts")
    for name in ("task_bank_sha256",):
        if not isinstance(receipt.get(name),str) or not re.fullmatch(r"[0-9a-f]{64}",receipt[name]):
            raise ValueError("missing exact task bank digest")
    if (not isinstance(receipt.get("model_identity_supplied_not_attested"),str)
            or not re.fullmatch(r"[A-Za-z0-9:._/-]{1,200}",
                                receipt["model_identity_supplied_not_attested"])):
        raise ValueError("operator-supplied model identity is invalid")
    if (receipt.get("probe_mode")!="in_context_only"
            or receipt.get("source_of_answers")!="caller_transport"):
        raise ValueError("probe type differs")
    gains=receipt.get("improved_case_ids")
    losses=receipt.get("regressed_case_ids")
    for value in (gains,losses):
        if (not isinstance(value,list) or len(value)>count
                or value!=sorted(set(value))
                or any(not isinstance(s,str)
                       or re.fullmatch(r"[a-z][a-z0-9_.-]{3,63}",s) is None
                       for s in value)):
            raise ValueError("invalid bounded heldout case identity list")
    if set(gains)&set(losses):
        raise ValueError("a case cannot improve and regress simultaneously")
    if len(gains)-len(losses)!=receipt["delta_correct"]:
        raise ValueError("gain/loss ledger does not reconcile")
    if (not isinstance(receipt.get("not_established"),list)
            or receipt["not_established"]!=[
                "generalization","causal_learning","persistent_retention","statistical_significance"
            ]):
        raise ValueError("limitations are required")
    encoded=(json.dumps(receipt,sort_keys=True,ensure_ascii=False,
                        separators=(",",":"),allow_nan=False)+"\n").encode()
    if len(encoded)>16384:
        raise ValueError("evaluation receipt oversized")
    return encoded


def persist_paired_evaluation(registry,project_id,logical_path,receipt):
    """Write one versioned artifact through an existing registered project."""
    if (not isinstance(project_id,str) or not 1<=len(project_id)<=120
            or not isinstance(logical_path,str) or not logical_path.startswith("research/learning/")
            or ".." in logical_path.split("/")
            or len(logical_path)>256
            or not logical_path.endswith(".json")):
        raise ValueError("registered project and learning artifact path required")
    content=canonical_receipt(receipt)
    digest=sha256(content).hexdigest()
    saved=registry.put_artifact(project_id,logical_path,content,"application/json")
    if saved!=digest or not registry.verify_artifact(saved):
        raise RuntimeError("canonical training evaluation artifact failed verification")
    history=registry.artifact_history(project_id,logical_path)
    matching=[item for item in history if item.get("digest")==digest]
    if not matching:
        raise RuntimeError("canonical evaluation artifact history missing")
    identity=registry.artifact_ref(project_id,logical_path,matching[-1]["version"])
    if identity.get("sha256")!=digest:
        raise RuntimeError("canonical training evaluation identity differs")
    return {"artifact_ref":identity,"sha256":digest,
            "evidence_class":"self_reported_observed_model_outputs",
            "model_weights_updated":False,"mastery_qualified":False}


__all__=["canonical_receipt","persist_paired_evaluation"]
