"""VerifierBench-inspired calibration before trusting an executable verifier.

A verifier that rejects every answer appears safe if tested only on bad
answers. Calibrate *separately supplied, trusted* verifier callables against
positive canonical, independently valid alternative, and negative cases.

This checks test-set performance only, not mathematical correctness, security,
model quality, or an LLM-generated verifier's sandbox. Model-authored verifier
code must never be executed through this module.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Callable, Sequence


@dataclass(frozen=True)
class VerificationCase:
    case_id: str
    task_id: str
    kind: str  # canonical_valid | alternative_valid | invalid
    candidate: str


_ALLOWED_KINDS = {"canonical_valid","alternative_valid","invalid"}


def _canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,
                      separators=(",",":"),allow_nan=False).encode()


def calibrate(verifier: Callable[[str,str], bool],
              cases: Sequence[VerificationCase]) -> dict:
    """Compute a fail-closed exact-fixture confusion matrix.

    At least one valid alternative and one invalid answer per task are required.
    No live model calls or tool use. Untrusted verifier *source code* is
    forbidden; caller must supply a trusted, pre-installed callable.
    """
    if not callable(verifier) or not isinstance(cases,(tuple,list)) or not 3 <= len(cases) <= 128:
        raise ValueError("bounded trusted verifier and test cases required")
    counts={}
    seen=set()
    measured=[]
    for case in cases:
        if not isinstance(case,VerificationCase):
            raise ValueError("test cases must be typed")
        if (not isinstance(case.case_id,str)
                or re.fullmatch(r"[a-z][a-z0-9_.-]{2,63}",case.case_id) is None
                or not isinstance(case.task_id,str)
                or re.fullmatch(r"[a-z][a-z0-9_.-]{2,63}",case.task_id) is None
                or case.kind not in _ALLOWED_KINDS
                or not isinstance(case.candidate,str)
                or not 0<len(case.candidate)<=2048
                or case.case_id in seen):
            raise ValueError("malformed, repeated, or unbounded calibration case")
        seen.add(case.case_id)
        pair=counts.setdefault(case.task_id,{key:0 for key in _ALLOWED_KINDS})
        pair[case.kind]+=1
        try:
            accepted=verifier(case.task_id,case.candidate)
        except Exception as exc:
            raise RuntimeError("verifier threw during bounded calibration") from exc
        if type(accepted) is not bool:
            raise ValueError("verifier must return an exact Boolean")
        expected=case.kind!="invalid"
        measured.append({"case_id":case.case_id,"task_id":case.task_id,
                         "kind":case.kind,"expected":expected,
                         "accepted":accepted})
    if len(counts)>32 or any(
        row["canonical_valid"]<1 or row["alternative_valid"]<1 or row["invalid"]<1
        for row in counts.values()
    ):
        raise ValueError("each task must include canonical, alternative and negative controls")
    tp=sum(x["accepted"] and x["expected"] for x in measured)
    fn=sum(not x["accepted"] and x["expected"] for x in measured)
    fp=sum(x["accepted"] and not x["expected"] for x in measured)
    tn=sum(not x["accepted"] and not x["expected"] for x in measured)
    alt_rejected=sum(not x["accepted"] and x["kind"]=="alternative_valid"
                     for x in measured)
    if not (tp+fn>0 and fp+tn>0):
        raise ValueError("both positive and negative controls required")
    false_negative_ids=[x["case_id"] for x in measured
                        if x["expected"] and not x["accepted"]]
    false_positive_ids=[x["case_id"] for x in measured
                        if not x["expected"] and x["accepted"]]
    case_records=[{"case_id":x["case_id"],"task_id":x["task_id"],
                   "kind":x["kind"],
                   "candidate_sha256":sha256(
                       next(c.candidate for c in cases if c.case_id==x["case_id"]).encode()
                   ).hexdigest()}
                  for x in measured]
    verdict=(fp==0 and fn==0)
    return {"schema":"merlin-verifier-calibration/1",
            "case_set_sha256":sha256(_canonical(case_records)).hexdigest(),
            "task_count":len(counts),"case_count":len(cases),
            "true_positive":tp,"false_negative":fn,
            "true_negative":tn,"false_positive":fp,
            "valid_alternatives_rejected":alt_rejected,
            "balanced_accuracy":round((tp/(tp+fn)+tn/(tn+fp))/2,6),
            "false_negative_case_ids":false_negative_ids,
            "false_positive_case_ids":false_positive_ids,
            "accepted_for_tested_cases":verdict,
            "validity_established_beyond_test_cases":False,
            "automated_promotion_authority":False}


__all__=["VerificationCase","calibrate"]
