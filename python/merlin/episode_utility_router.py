"""MemRL/ACE-inspired *nonparametric* strategy utility shortlist.

Observes bounded, source-pinned outcome metadata from the EXISTING registry.
Two stages: task-tag match first; simple Laplace-smoothed past success ratio
second. It neither learns model weights nor proves outcomes are authentic.
The calling host must authenticate feedback before storing the evidence.
"""
from __future__ import annotations
from hashlib import sha256
import json
import re
from typing import Mapping, Sequence, Callable

from .artifact_ref import ArtifactRef
from .project_registry import MerlinRegistry

SCHEMA="merlin-strategy-episode/1"
OUTPUT_SCHEMA="merlin-episode-utility-shortlist/1"
MAX_EPISODES=64
_REQUIRED={"schema","strategy_id","tags","outcome","feedback_class"}


def _tags(values):
    if (not isinstance(values,list) or not 1<=len(values)<=10
            or any(not isinstance(x,str)
                   or re.fullmatch(r"[a-z][a-z0-9_]{2,31}",x) is None
                   for x in values)
            or len(values)!=len(set(values))):
        raise ValueError("bounded distinct search tags required")
    return values


def _canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(",",":"),
                       ensure_ascii=False,allow_nan=False)+"\n").encode()


def _episode(content):
    if not isinstance(content,bytes) or len(content)>2048:
        raise ValueError("small canonical episode required")
    body=json.loads(content)
    if (not isinstance(body,dict) or set(body)!=_REQUIRED
            or body.get("schema")!=SCHEMA or
            not isinstance(body.get("strategy_id"),str) or
            re.fullmatch(r"[a-z][a-z0-9_.-]{2,63}",body["strategy_id"]) is None
            or body.get("outcome") not in ("success","failure")
            or body.get("feedback_class")!="unverified_observed"):
        raise ValueError("typed unverified outcome metadata required")
    _tags(body.get("tags"))
    if _canonical(body)!=content:
        raise ValueError("episode metadata must be canonical and immutable")
    return body


def shortlist(registry: MerlinRegistry, *, project_id: str,
              query_tags: list[str], episode_refs: Sequence[Mapping],
              authorize: Callable[[str, dict], bool], max_strategies=5):
    """Return bounded research candidates, not executable strategies."""
    if not isinstance(registry,MerlinRegistry):
        raise ValueError("reuse existing Merlin registry")
    _tags(query_tags)
    if (not isinstance(project_id,str) or not project_id.strip()
            or type(max_strategies) is not int or not 1<=max_strategies<=10
            or not isinstance(episode_refs,(list,tuple))
            or not 1<=len(episode_refs)<=MAX_EPISODES):
        raise ValueError("bounded project, source list and result cap required")
    if not callable(authorize):
        raise ValueError("host authorization callback required")
    # First authorize the COMPLETE bounded input set. A late denial or
    # duplicate may never cause earlier references to be read as a side effect.
    seen=set()
    admitted=[]
    for rawref in episode_refs:
        ref=ArtifactRef.from_mapping(rawref).to_dict()
        if ref["project_id"]!=project_id:
            raise PermissionError("cross-project episode evidence not permitted")
        key=json.dumps(ref,sort_keys=True)
        if key in seen:
            raise ValueError("duplicate artifact reference")
        seen.add(key)
        if authorize("episode_source",dict(ref)) is not True:
            raise PermissionError("host denied exact episode source")
        admitted.append(ref)
    group={}
    scanned=0
    matched=0
    for ref in admitted:
        content=registry.read_artifact_ref(ref,max_bytes=2048)["content"]
        record=_episode(content)
        scanned+=1
        overlap=set(record["tags"]) & set(query_tags)
        if not overlap:
            continue
        matched+=1
        entry=group.setdefault(record["strategy_id"],
                               {"success":0,"failure":0,
                                "evidence_refs":[],"tags":set(),"hits":0})
        entry[record["outcome"]]+=1
        entry["hits"]+=len(overlap)
        entry["tags"].update(overlap)
        entry["evidence_refs"].append(ref)
    candidates=[]
    for strategy_id,item in group.items():
        total=item["success"]+item["failure"]
        # A bounded heuristic, not a calibrated probability or reward model.
        utility=round((item["success"]+1)/(total+2),6)
        candidates.append({"strategy_id":strategy_id,
                           "matched_tags":sorted(item["tags"]),
                           "feedback_count":total,
                           "success_count":item["success"],
                           "failure_count":item["failure"],
                           "tag_matches":item["hits"],
                           "laplace_utility_heuristic":utility,
                           "episode_refs":item["evidence_refs"]})
    candidates.sort(key=lambda x:(-x["laplace_utility_heuristic"],
                                  -x["feedback_count"],
                                  -x["tag_matches"],x["strategy_id"]))
    selected=candidates[:max_strategies]
    return {"schema":OUTPUT_SCHEMA,
            "query_tags":list(query_tags),
            "episode_refs_examined":scanned,
            "episode_refs_matching_query":matched,
            "strategies_matching_query":len(candidates),
            "selected_strategies":selected,
            "omitted_strategy_count":len(candidates)-len(selected),
            "selected_strategy_ids":[x["strategy_id"] for x in selected],
            "feedback_origin":"unverified_observed",
            "utility_is_calibrated_probability":False,
            "model_weights_updated":False,
            "strategies_executed":False,
            "strategy_quality_established":False,
            "promotion_authority":False}


__all__=["SCHEMA","OUTPUT_SCHEMA","shortlist"]
