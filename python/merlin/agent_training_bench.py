"""Small, reproducible Merlin practice/evaluation protocol; no weight training.

Training examples are generated from authored synthetic cases only. Heldout
answers never appear in the learning prompt. Evaluation is offline and makes
no model-quality claim unless real model responses are supplied.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Mapping


@dataclass(frozen=True)
class Task:
    task_id: str
    domain: str
    split: str
    question: str
    reference: str
    rationale: str


TASKS = (
    Task("arith.practice.1","arithmetic","practice",
         "Compute 8 times 9. Answer with a number only.","72","8 multiplied by 9 equals 72."),
    Task("arith.practice.2","arithmetic","practice",
         "Compute 12 times 4. Answer with a number only.","48","12 multiplied by 4 equals 48."),
    Task("arith.holdout.1","arithmetic","holdout",
         "Compute 7 times 13. Answer with a number only.","91","7 multiplied by 13 equals 91."),
    Task("arith.holdout.2","arithmetic","holdout",
         "Compute 9 times 14. Answer with a number only.","126","9 multiplied by 14 equals 126."),
    Task("simplex.practice.1","simplex","practice",
         "Normalize the nonnegative weights 1,1,2. Use reduced fractions separated by commas.",
         "1/4,1/4,1/2","Divide each weight by 4."),
    Task("simplex.holdout.1","simplex","holdout",
         "Normalize the nonnegative weights 2,3,5. Use reduced fractions separated by commas.",
         "1/5,3/10,1/2","Divide each weight by 10."),
    Task("dc.practice.1","ideal_dc","practice",
         "Ideal DC only: 12 volts across a 6-ohm resistor. Current in amperes? Number only.",
         "2","Ohm's law gives I=V/R."),
    Task("dc.holdout.1","ideal_dc","holdout",
         "Ideal DC only: 10 volts across a 4-ohm resistor. Current in amperes? Number only.",
         "2.5","Ohm's law gives I=V/R."),
    Task("bytes.practice.1","memory","practice",
         "1024 elements at 4 bytes each. Total bytes? Number only.",
         "4096","Multiply element count by bytes per element."),
    Task("bytes.holdout.1","memory","holdout",
         "1536 elements at 8 bytes each. Total bytes? Number only.",
         "12288","Multiply element count by bytes per element."),
    Task("titan.practice.1","titan_scope","practice",
         "Can a structural envelope schema test prove that encryption is secure? Reply yes or no.",
         "no","Structural conformance is not cryptographic security."),
    Task("titan.holdout.1","titan_scope","holdout",
         "Do placeholder ciphertext test vectors establish authenticated encryption security? Reply yes or no.",
         "no","Placeholder vectors are not AEAD known-answer tests."),
    Task("physics.practice.1","simulation_scope","practice",
         "Does a simulated resistor-network result alone prove the physical device is safe? Reply yes or no.",
         "no","An ideal model excludes physical effects and verification."),
    Task("physics.holdout.1","simulation_scope","holdout",
         "Does a simulated parallax effect alone establish a new hardware capability? Reply yes or no.",
         "no","Numerical hypotheses require independent empirical observations."),
)


def validate_bank(tasks=TASKS):
    if not isinstance(tasks,(tuple,list)) or not 1 <= len(tasks) <= 256:
        raise ValueError("bounded task collection required")
    names=set()
    splits={"practice":set(),"holdout":set()}
    for item in tasks:
        if not isinstance(item,Task) or item.split not in splits:
            raise ValueError("invalid task type or split")
        if (not re.fullmatch(r"[a-z][a-z0-9_.-]{3,63}",item.task_id)
                or item.task_id in names
                or not re.fullmatch(r"[a-z][a-z0-9_]{2,31}",item.domain)):
            raise ValueError("invalid or duplicate task identity")
        names.add(item.task_id)
        for value in (item.question,item.reference,item.rationale):
            if not isinstance(value,str) or not value.strip() or len(value)>500:
                raise ValueError("invalid bounded reference task text")
        splits[item.split].add(item.domain)
    if splits["practice"]!=splits["holdout"]:
        raise ValueError("all domains need disjoint practice and heldout questions")
    return True


def bank_identity(tasks=TASKS):
    validate_bank(tasks)
    raw=json.dumps([item.__dict__ for item in tasks],sort_keys=True,
                   separators=(",",":"),ensure_ascii=False).encode()
    return sha256(raw).hexdigest()


def practice_context(domain, *, task_id, max_examples=2, tasks=TASKS):
    """Only public synthetic PRACTICE references may appear in context."""
    validate_bank(tasks)
    if not isinstance(domain,str) or domain not in {x.domain for x in tasks}:
        raise ValueError("unknown domain")
    if type(max_examples) is not int or not 1 <= max_examples <= 2:
        raise ValueError("invalid example budget")
    requested=next((t for t in tasks if t.task_id==task_id),None)
    if requested is None or requested.domain!=domain or requested.split!="holdout":
        raise ValueError("practice prompt requires an exact heldout target")
    demonstrations=[x for x in tasks if x.domain==domain and x.split=="practice"]
    text=["You are Merlin. Give only the answer format requested.",
          "Practice examples are illustrative, not evidence of tool execution."]
    for item in demonstrations[:max_examples]:
        text.extend(("Practice: "+item.question,"Reference answer: "+item.reference))
    text.append("New question: "+requested.question)
    # Critical: never interpolate heldout references into the model prompt.
    return "\n".join(text)


def score_answer(task_id, response, *, tasks=TASKS):
    """Score one observed response; do not claim competence or training."""
    validate_bank(tasks)
    task=next((t for t in tasks if t.task_id==task_id),None)
    if task is None or task.split not in ("holdout","practice"):
        raise ValueError("unknown task")
    if not isinstance(response,str) or not 1 <= len(response)<=4096:
        raise ValueError("response must be bounded text")
    cleaned=response.strip().lower().replace(" ","")
    expected=task.reference.lower().replace(" ","")
    correct=cleaned==expected
    return {"task_id":task_id,"domain":task.domain,"split":task.split,
            "correct":correct,"response_sha256":sha256(response.encode()).hexdigest(),
            "response_chars":len(response),"model_weights_updated":False,
            "mastery_qualified":False}


def practice_feedback(task_id,response,*,tasks=TASKS):
    """Supervised feedback for a practice item only; heldout remains blind."""
    task=next((x for x in tasks if x.task_id==task_id),None)
    if task is None or task.split!="practice":
        raise ValueError("feedback must not reveal heldout references")
    result=score_answer(task_id,response,tasks=tasks)
    return {"task_id":task_id,"correct":result["correct"],
            "reference":task.reference,"explanation":task.rationale,
            "teaching_only":True,"model_weights_updated":False}


def evaluate_holdout(responses: Mapping[str,str],*,tasks=TASKS):
    validate_bank(tasks)
    if not isinstance(responses,Mapping) or len(responses)>256:
        raise ValueError("bounded response mapping required")
    holdouts={x.task_id:x for x in tasks if x.split=="holdout"}
    if not set(responses).issubset(holdouts):
        raise ValueError("unknown or practice task in heldout results")
    graded=[score_answer(key,responses[key],tasks=tasks) for key in sorted(responses)]
    return {"schema":"merlin-synthetic-competency-eval/1",
            "task_bank_sha256":bank_identity(tasks),"heldout_count":len(holdouts),
            "observed_count":len(graded),"missing_count":len(holdouts)-len(graded),
            "correct_count":sum(row["correct"] for row in graded),
            "results":graded,"model_weights_updated":False,
            "model_quality_qualified":False,
            "independent_assessment_required":True}


def compare_practice_effect(baseline: Mapping[str,str],
                            practiced: Mapping[str,str],*,tasks=TASKS):
    """Paired blind scores over precisely the same heldout cases.

    Evidence of a score change is NOT evidence of a weight update, persistent
    learning, statistical significance or general improvement.
    """
    validate_bank(tasks)
    if not isinstance(baseline,Mapping) or not isinstance(practiced,Mapping):
        raise ValueError("paired results must be bounded response mappings")
    reference={x.task_id for x in tasks if x.split=="holdout"}
    if set(baseline)!=reference or set(practiced)!=reference:
        raise ValueError("pairing must cover every heldout task exactly")
    initial=evaluate_holdout(baseline,tasks=tasks)
    guided=evaluate_holdout(practiced,tasks=tasks)
    b={x["task_id"]:x for x in initial["results"]}
    p={x["task_id"]:x for x in guided["results"]}
    improved=sorted(k for k in reference if not b[k]["correct"] and p[k]["correct"])
    regressed=sorted(k for k in reference if b[k]["correct"] and not p[k]["correct"])
    return {"schema":"merlin-paired-practice-effect/1",
            "task_bank_sha256":initial["task_bank_sha256"],
            "heldout_count":len(reference),
            "baseline_correct":initial["correct_count"],
            "after_practice_correct":guided["correct_count"],
            "delta_correct":guided["correct_count"]-initial["correct_count"],
            "improved_case_ids":improved,
            "regressed_case_ids":regressed,
            "model_weights_updated":False,"mastery_qualified":False,
            "not_established":["generalization","causal_learning",
                               "persistent_retention","statistical_significance"]}



__all__=["Task","TASKS","validate_bank","bank_identity","practice_context",
         "score_answer","practice_feedback","evaluate_holdout","compare_practice_effect"]
