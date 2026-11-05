#!/usr/bin/env python3
"""Send a rights-cleared historical-science dossier through Merlin with a validated engineering plan."""
from __future__ import annotations
import argparse, hashlib, json, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from merlin_problem_reframing import template as reframe_template

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
      "objective":"Analyze the supplied primary-source dossier to improve Merlin's ideonomy and scientific reasoning.",
      "required_outputs":[
        "separate direct source observations from historical interpretation and new conjecture",
        "identify the research problem and historical context",
        "extract methods, instruments, evidence types, assumptions and limitations",
        "map the work to existing discipline branches and neighboring fields",
        "propose no more than 8 cross-disciplinary ideonomy connections, each labeled analogy, hypothesis or formalizable conjecture",
        "for each connection, state a falsifiable question or precise formal object and a counterexample or disconfirmation path",
        "identify omitted predecessors, collaborators, alternative explanations and edition/translation caveats",
        "suggest one measurable improvement to Merlin's research process"
      ],
      "citation_rule":"Every historical or factual claim must point to a supplied citation URL and section/page/line location. If support is missing, say unknown. Never invent private thoughts or quotations.",
      "epistemic_rule":"Do not label speculative connections as established science. Distinguish modern consensus from period beliefs.",
      "response_format":"Return concise JSON with keys: source_digest, historical_context, methods, evidence, limitations, discipline_links, ideonomy_candidates, merlin_improvements, unsupported_questions.",
      "promotion":"candidate_only","authority_delta":0,"dossier":dossier
    }
    return "You are Merlin's bounded science-history and ideonomy research worker. Follow this task contract exactly.\n"+json.dumps(instructions,ensure_ascii=False,indent=2),digest


def build_engineering_plan(dossier: dict) -> dict:
    work=dossier.get("work",{})
    domain_text=str(work.get("domain","mathematics and science history"))
    raw_id=str(dossier.get("dossier_id") or "source").lower()
    task_id="science-ideonomy-"+re.sub(r"[^a-z0-9-]+","-",raw_id).strip("-")[:64]
    rp=reframe_template(task_id)
    rp["original_problem"]="Analyze the source dossier and identify defensible cross-disciplinary connections."
    rp["decomposition"]["subproblems"][0].update(objective="Extract source-grounded claims, methods and context",interface="Cited evidence ledger",acceptance="Claims are labeled and traceable to supplied citations")
    rp["decomposition"]["subproblems"][1].update(objective="Compare candidate cross-disciplinary mappings",interface="Evidence ledger plus candidate concepts",acceptance="Each mapping has a transfer class and disconfirmation test")
    rp["representations"][0].update(encoding="Primary-source evidence and historical analysis",mapping="Identity with the dossier's cited claims",preserved_invariants=["source attribution","edition context"],lost_information=[],validity_conditions=["citations resolve"],validation_method="Verify source spans")
    rp["representations"][1].update(encoding="Discipline and concept graph",mapping="Concepts map to nodes; cited relations map to typed edges",preserved_invariants=["explicit relations","provenance links"],lost_information=["narrative sequence"],validity_conditions=["edges retain citations"],non_transferable_properties=["Graph adjacency does not prove conceptual equivalence or causation."],validation_method="Check every edge against cited source evidence")
    return {
      "plan_version":1,"task_id":task_id,"problem_representation":rp,
      "objective":"Produce a source-grounded historical and ideonomy analysis without promoting claims.",
      "domain_scope":{"primary_domain":"humanities-philosophy","secondary_domains":["mathematics","physical","life"],"subsystems":["history of science","philosophy of science","primary-source analysis","ideonomy"],"excluded_domains":["unrelated operational systems"],"scope_rationale":"Primary scope is history and philosophy of inquiry; neighboring fields are contextual. Source domain label: "+domain_text},
      "requirements":[
        {"id":"REQ-001","statement":"Separate direct source evidence from interpretation and conjecture.","acceptance":"Every claim is epistemically labeled and cited or marked unknown."},
        {"id":"REQ-002","statement":"Compare historical context, methods, assumptions and limitations.","acceptance":"The output identifies evidence, alternatives, collaborators and edition caveats."},
        {"id":"REQ-003","statement":"Generate bounded ideonomy candidates.","acceptance":"At most eight candidates, each with a falsifiable question and disconfirmation path."}
      ],
      "assumptions":["The supplied dossier accurately identifies its source edition and citations; verify rather than presume."],
      "constraints":["Dossier input <= 256000 bytes","Candidate-only output","No canonical graph writes or authority changes"],
      "dependencies":["Rights-cleared dossier","Traceable primary-source citations","Configured local Merlin runtime"],
      "reasoning_plan":{"inductive":"Extract patterns only from cited passages; state coverage and limits.","deductive":"Make premises, inference rules and formal consequences explicit.","abductive":"Compare at least two plausible historical or conceptual explanations.","disconfirmation":"Name counterevidence, missing sources and tests that would reject each proposed connection."},
      "design":{"method":"Primary-source analysis with explicit historical and epistemic separation.","alternatives":["Source-only summary","Comparative historical analysis"],"limitations":"A dossier is a selected sample, not the complete historical record.","bias_review":{"possible_biases":["selection_bias","survivorship_bias","confirmation_bias","historical_presentism","translation_or_transcription_bias"],"possible_fallacies":["appeal_to_authority","hasty_generalization","false_analogy"],"checks":["seek overlooked predecessors and critics","compare editions and translations","separate period beliefs from modern consensus","search for disconfirming evidence"]}},
      "resource_budget":{"max_runtime_seconds":900,"max_memory_mb":2048,"max_disk_bytes":10485760,"max_input_bytes":262144},
      "verification":{"tests":["source digest matches dossier","claims cite supplied source spans","candidate count <= 8","no canonical writes"],"independent_check":"Human domain reviewer checks source citations, historical context and mathematical or empirical claims."},
      "rollback":"Quarantine or delete the unreviewed candidate and plan sidecar; canonical records remain untouched."
    }


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dossier",type=Path,required=True)
    p.add_argument("--runtime",type=Path,required=True)
    p.add_argument("--role",choices=("controller","coder","learner","math"),default="controller")
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--timeout",type=int,default=600)
    a=p.parse_args()
    try:
        root=Path(__file__).resolve().parents[1]
        dossier=json.loads(a.dossier.resolve().read_text(encoding="utf-8"))
        prompt,digest=build_packet(dossier)
        plan=build_engineering_plan(dossier)
        plan_path=a.out.resolve().with_suffix(a.out.suffix+".engineering-plan.json")
        plan_path.parent.mkdir(parents=True,exist_ok=True)
        plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        validator=Path(__file__).resolve().with_name("merlin_engineering_plan.py")
        validation=subprocess.run([sys.executable,str(validator),"--validate",str(plan_path)],capture_output=True,text=True,check=False)
        if validation.returncode != 0: raise ValueError("generated engineering plan failed validation: "+validation.stdout+validation.stderr)
        command=[sys.executable,str(root/"python/orchestrator.py"),"--runtime",str(a.runtime.resolve()),"--role",a.role,"--task",prompt,"--plan",str(plan_path)]
        result=subprocess.run(command,capture_output=True,text=True,timeout=max(30,min(a.timeout,900)),check=False,cwd=root)
        response=result.stdout[-MAX_RESPONSE_CHARS:]
        plan_raw=json.dumps(plan,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
        record={
          "schema_version":1,"record_type":"merlin.science.ideonomy-candidate",
          "dossier_id":dossier.get("dossier_id"),"source_digest_sha256":digest,
          "engineering_plan_path":str(plan_path),"engineering_plan_sha256":hashlib.sha256(plan_raw).hexdigest(),
          "source_citations":dossier.get("citations",[]),"runtime_role":a.role,
          "runtime_exit_code":result.returncode,"runtime_response":response,
          "runtime_stderr_tail":result.stderr[-4000:],"created_at":datetime.now(timezone.utc).isoformat(),
          "candidate_status":"needs_human_review" if result.returncode==0 else "runtime_failed",
          "promotion_state":"not_eligible","canonical_research_graph_write":False,"authority_delta":0
        }
        out=a.out.resolve()
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(record,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print(json.dumps({"ok":result.returncode==0,"dossier_id":record["dossier_id"],"source_digest_sha256":digest,"engineering_plan_sha256":record["engineering_plan_sha256"],"candidate_status":record["candidate_status"],"promotion_state":record["promotion_state"]},sort_keys=True))
        return 0 if result.returncode==0 else 2
    except Exception as exc:
        print(json.dumps({"ok":False,"error":str(exc),"error_type":type(exc).__name__},sort_keys=True),file=sys.stderr)
        return 2


if __name__=="__main__": raise SystemExit(main())
