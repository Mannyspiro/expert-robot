"""Independent arithmetic/structure review of a private Merlin context pilot.

Evaluates a trusted RECEIPT BYTES once separately acquired. It cannot
authenticate GitHub/model artifacts, verify true model provenance, rerun tasks
or establish general learning. Its main role is to prevent time/cache
confounding and aggregate-only claims from being treated as release evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
from statistics import median


SCHEMA="merlin-private-context-ablation/1"
_KINDS={"full","selected"}
_CASE_KEYS={"id","source_id","source_sha256","full","selected"}
_METRIC_KEYS={"correct","answer_sha256","latency_seconds",
              "prompt_bytes","prompt_sha256","prompt_tokens"}


def _digest(value):
    return isinstance(value,str) and len(value)==64 and all(c in "0123456789abcdef" for c in value)


def _bounded_int(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def _bounded_float(value, minimum, maximum):
    return type(value) in (int,float) and math.isfinite(value) and minimum <= value <= maximum


def inspect_context_receipt(packet):
    """Recompute metrics from each case and reject contradictory summaries.

    The receipt is untrusted until independently bound to a specific run,
    source hashes and model identity. No new memory/weights/permissions.
    """
    if not isinstance(packet,dict) or packet.get("schema")!=SCHEMA:
        raise ValueError("exact context pilot v1 receipt required")
    if packet.get("status")!="observed" or packet.get("production_qualified") is not False:
        raise ValueError("blocked or promotion-claiming pilot receipt rejected")
    if (packet.get("model_weights_updated") is not False
            or packet.get("model_quality_improvement_established") is not False
            or packet.get("registry_router_integration_tested") is not False):
        raise ValueError("pilot must not claim training or canonical integration")
    if packet.get("source_selection")!="frozen-tag-lookup-not-canonical-registry-router":
        raise ValueError("pilot source selection mode differs")
    cases=packet.get("cases")
    if not isinstance(cases,list) or not 4 <= len(cases) <= 32:
        raise ValueError("4 to 32 paired cases required")
    if (packet.get("task_count")!=len(cases)
            or packet.get("model_calls")!=2*len(cases)):
        raise ValueError("paired case count differs")
    seen=set()
    sums={key:{"tokens":0,"bytes":0,"seconds":0.0,"correct":0}
          for key in _KINDS}
    case_correctness=[]
    latency={}
    for row in cases:
        if not isinstance(row,dict) or set(row)!=_CASE_KEYS:
            raise ValueError("exact case fields required")
        case_id=row["id"]
        if not isinstance(case_id,str) or not 3<=len(case_id)<=64 or case_id in seen:
            raise ValueError("duplicate or invalid context case id")
        seen.add(case_id)
        if (not isinstance(row["source_id"],str)
                or not 1<=len(row["source_id"])<=32
                or not _digest(row["source_sha256"])):
            raise ValueError("invalid source identity or digest")
        case_result={}
        for mode in _KINDS:
            trial=row[mode]
            if not isinstance(trial,dict) or set(trial)!=_METRIC_KEYS:
                raise ValueError("complete bounded model trial fields required")
            if (type(trial["correct"]) is not bool
                    or not _digest(trial["answer_sha256"])
                    or not _digest(trial["prompt_sha256"])
                    or not _bounded_int(trial["prompt_bytes"],1,8192)
                    or not _bounded_int(trial["prompt_tokens"],1,65536)
                    or not _bounded_float(trial["latency_seconds"],0,120)):
                raise ValueError("invalid measured model trial data")
            sums[mode]["tokens"]+=trial["prompt_tokens"]
            sums[mode]["bytes"]+=trial["prompt_bytes"]
            sums[mode]["seconds"]+=trial["latency_seconds"]
            sums[mode]["correct"]+=int(trial["correct"])
            case_result[mode]=trial["correct"]
        latency[case_id]=(row["full"]["latency_seconds"],
                          row["selected"]["latency_seconds"])
        case_correctness.append(case_result)
    regressions=sum(x["full"] and not x["selected"] for x in case_correctness)
    improvements=sum(not x["full"] and x["selected"] for x in case_correctness)
    keys={"full_correct":sums["full"]["correct"],
          "selected_correct":sums["selected"]["correct"],
          "regressed_count":regressions,
          "improved_count":improvements,
          "full_prompt_tokens":sums["full"]["tokens"],
          "selected_prompt_tokens":sums["selected"]["tokens"],
          "full_prompt_bytes":sums["full"]["bytes"],
          "selected_prompt_bytes":sums["selected"]["bytes"]}
    for key,value in keys.items():
        if packet.get(key)!=value:
            raise ValueError("pilot summary differs from its underlying case ledger: "+key)
    for mode in _KINDS:
        field=mode+"_wall_seconds"
        if not _bounded_float(packet.get(field),0,120*len(cases)):
            raise ValueError("missing bounded wall-time sum")
        if abs(packet[field]-round(sums[mode]["seconds"],3))>0.001:
            raise ValueError("wall-time sum differs from measured cases")
    reduction=round(
        1-sums["selected"]["tokens"]/sums["full"]["tokens"],5)
    if not _bounded_float(packet.get("prompt_token_savings_fraction"),-10,1):
        raise ValueError("token saving must be present")
    if abs(reduction-packet["prompt_token_savings_fraction"])>0.00001:
        raise ValueError("reported token saving differs from per-case tally")
    passed=(regressions==0 and sums["selected"]["correct"]==len(cases)
            and reduction>=.2)
    if packet.get("pilot_gate_met") is not passed:
        raise ValueError("claimed pilot qualification gate differs")
    # Large cold-start outlier + later full-context overlap makes aggregate
    # timings insufficient evidence of steady-state speed improvement.
    full_lat=[row["full"]["latency_seconds"] for row in cases]
    selected_lat=[row["selected"]["latency_seconds"] for row in cases]
    first_full_outlier=(len(full_lat)>=4
                        and full_lat[0]>3*median(full_lat[1:]))
    if len(set(t[0] for t in latency.values()))!=len(latency):
        raise RuntimeError("unexpected case latency identity collision")
    return {
        "schema":"merlin-independent-context-pilot-review/1",
        "task_count":len(cases),
        "paired_correctness_preserved":regressions==0,
        "all_selected_answers_correct":sums["selected"]["correct"]==len(cases),
        "verified_full_correct":sums["full"]["correct"],
        "verified_selected_correct":sums["selected"]["correct"],
        "verified_prompt_token_savings_fraction":reduction,
        "token_measurements_reconciled":True,
        "large_first_full_request_latency_outlier":first_full_outlier,
        "median_later_full_latency_seconds":round(median(full_lat[1:]),3),
        "median_selected_latency_seconds":round(median(selected_lat),3),
        "latency_speedup_generalization_qualified":False,
        "source_selector_is_production_registry":False,
        "run_or_weight_identity_independently_attested":False,
        "broad_model_quality_improvement_established":False,
        "model_weights_updated":False,
        "production_qualified":False,
        "pilot_results_eligible_for_further_evaluation":passed,
    }


__all__=["SCHEMA","inspect_context_receipt"]
