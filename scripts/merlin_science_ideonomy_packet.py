#!/usr/bin/env python3
"""Send a rights-cleared historical-science dossier through Merlin's existing runtime.

The response is an unreviewed ideonomy candidate. This bridge cannot write to
the verified theorem graph, promote claims, or change execution authority.
"""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

MAX_DOSSIER_BYTES=256_000
MAX_RESPONSE_CHARS=24_000

def build_packet(dossier: dict) -> tuple[str,str]:
    raw=json.dumps(dossier,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    if len(raw)>MAX_DOSSIER_BYTES: raise ValueError("dossier exceeds bounded intake size")
    work=dossier.get("work",{})
    refs=dossier.get("citations",[])
    if not work.get("url") or not refs: raise ValueError("dossier requires a primary-source URL and citations")
    digest=hashlib.sha256(raw).hexdigest()
    instructions={
      "task":"historical_science_ideonomy_analysis",
      "objective":"Analyze the supplied public-domain primary-source dossier to improve Merlin's ideonomy and scientific reasoning.",
      "required_outputs":[
        "separate direct source observations from historical interpretation and new conjecture",
        "identify the research problem and historical context",
        "extract methods, instruments, evidence types, assumptions and limitations",
        "map the work to existing discipline branches and neighboring fields",
        "propose no more than 8 cross-disciplinary ideonomy connections, each labeled analogy, hypothesis or formalizable conjecture",
        "for each connection, state a falsifiable question or precise formal object and a counterexample or disconfirmation path",
        "identify omitted predecessors, collaborators, alternative explanations and edition/translation caveats",
        "suggest one way Merlin's research workflow, source tracking or evaluation could improve"
      ],
      "citation_rule":"Every historical or factual claim must point to one of the supplied citation URLs and section/page/line locations. If support is missing, say unknown. Never invent private thoughts or quotations.",
      "epistemic_rule":"Do not label speculative connections as established science. Distinguish modern consensus from period beliefs.",
      "response_format":"Return concise JSON with keys: source_digest, historical_context, methods, evidence, limitations, discipline_links, ideonomy_candidates, merlin_improvements, unsupported_questions.",
      "promotion":"candidate_only",
      "authority_delta":0,
      "dossier":dossier
    }
    prompt="You are Merlin's bounded science-history and ideonomy research worker. Follow this task contract exactly.\n"+json.dumps(instructions,ensure_ascii=False,indent=2)
    return prompt,digest

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dossier",type=Path,required=True)
    p.add_argument("--runtime",type=Path,required=True)
    p.add_argument("--role",choices=("controller","coder","learner","math"),default="controller")
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--timeout",type=int,default=600)
    a=p.parse_args()
    try:
        dossier=json.loads(a.dossier.read_text(encoding="utf-8"))
        prompt,digest=build_packet(dossier)
        command=[sys.executable,"python/orchestrator.py","--runtime",str(a.runtime),"--role",a.role,"--task",prompt]
        result=subprocess.run(command,capture_output=True,text=True,timeout=max(30,min(a.timeout,900)),check=False)
        response=result.stdout[-MAX_RESPONSE_CHARS:]
        record={
          "schema_version":1,
          "record_type":"merlin.science.ideonomy-candidate",
          "dossier_id":dossier.get("dossier_id"),
          "source_digest_sha256":digest,
          "source_citations":dossier.get("citations",[]),
          "runtime_role":a.role,
          "runtime_exit_code":result.returncode,
          "runtime_response":response,
          "runtime_stderr_tail":result.stderr[-4000:],
          "created_at":datetime.now(timezone.utc).isoformat(),
          "candidate_status":"needs_human_review" if result.returncode==0 else "runtime_failed",
          "promotion_state":"not_eligible",
          "canonical_research_graph_write":False,
          "authority_delta":0
        }
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(record,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print(json.dumps({"ok":result.returncode==0,"dossier_id":record["dossier_id"],"source_digest_sha256":digest,"candidate_status":record["candidate_status"],"promotion_state":record["promotion_state"]},sort_keys=True))
        return 0 if result.returncode==0 else 2
    except Exception as exc:
        print(json.dumps({"ok":False,"error":str(exc),"error_type":type(exc).__name__},sort_keys=True),file=sys.stderr)
        return 2

if __name__=="__main__": raise SystemExit(main())
