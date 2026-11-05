"""Persistent, evidence-based learner model and Hermes lesson selection.

This is a local SQLite reference service. Attempts are append-only and
idempotent; estimates are transparent Beta-binomial summaries, not diagnoses.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
import math
import sqlite3
import time
from pathlib import Path
from typing import Any, Mapping

DIMENSIONS = {
    "recognition", "conceptual_explanation", "procedure",
    "representation_translation", "estimation_error_detection",
    "transfer", "proof_justification", "delayed_retention",
}
ATTEMPT_TOPIC = "merlin.learning.attempt"


class LearnerEventConflict(ValueError):
    pass


@dataclass(frozen=True)
class SkillEstimate:
    idea_id: str
    dimension: str
    mean: float
    uncertainty: float
    observations: int
    independent_sessions: int
    state: str


class LearnerStore:
    """Append-only attempt ledger with rebuildable skill summaries."""

    def __init__(self, database: str | Path):
        self.path = str(database)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS learner_attempts(
              attempt_id TEXT PRIMARY KEY, learner_id TEXT NOT NULL,
              idea_id TEXT NOT NULL, problem_id TEXT NOT NULL,
              problem_version TEXT NOT NULL, dimension TEXT NOT NULL,
              score REAL NOT NULL, session_id TEXT NOT NULL,
              submitted_at REAL NOT NULL, response_json TEXT NOT NULL,
              evidence_ref TEXT, rubric_version TEXT NOT NULL,
              delayed INTEGER NOT NULL, transfer INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS learner_attempt_lookup
              ON learner_attempts(learner_id,idea_id,dimension,submitted_at);
            """)
    
    def _connect(self):
        db=sqlite3.connect(self.path,timeout=30)
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA journal_mode=WAL")
        return db

    @staticmethod
    def _required(value: Any, name: str, limit: int=200) -> str:
        if not isinstance(value,str) or not value.strip() or len(value)>limit:
            raise ValueError(f"{name} must be a non-empty string of at most {limit} chars")
        return value.strip()

    def record_attempt(self, event: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(event,Mapping):
            raise ValueError("attempt event must be an object")
        learner=self._required(event.get("learner_id"),"learner_id")
        attempt=self._required(event.get("attempt_id"),"attempt_id")
        idea=self._required(event.get("idea_id"),"idea_id")
        problem=self._required(event.get("problem_id"),"problem_id")
        version=self._required(event.get("problem_version","1"),"problem_version")
        dimension=event.get("dimension")
        if dimension not in DIMENSIONS:
            raise ValueError("unsupported learner evidence dimension")
        score=event.get("score")
        if isinstance(score,bool) or not isinstance(score,(int,float)) or not 0<=score<=1:
            raise ValueError("score must be a number from 0 to 1")
        session=self._required(event.get("session_id"),"session_id")
        rubric=self._required(event.get("rubric_version","1"),"rubric_version")
        response=event.get("response",{})
        if not isinstance(response,Mapping):
            raise ValueError("response must be an object")
        evidence=event.get("evidence_ref")
        if evidence is not None:
            evidence=self._required(evidence,"evidence_ref",512)
        submitted=float(event.get("submitted_at",time.time()))
        if not math.isfinite(submitted) or submitted<=0:
            raise ValueError("submitted_at must be finite and positive")
        delayed=bool(event.get("delayed",False))
        transfer=bool(event.get("transfer",False))
        response_json=json.dumps(dict(response),sort_keys=True,allow_nan=False)
        if len(response_json)>100_000:
            raise ValueError("response artifact exceeds 100 KB")
        row=(attempt,learner,idea,problem,version,dimension,float(score),session,
             submitted,response_json,evidence,rubric,int(delayed),int(transfer))
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old=db.execute("SELECT * FROM learner_attempts WHERE attempt_id=?",(attempt,)).fetchone()
            if old:
                oldrow=tuple(old[k] for k in (
                  "attempt_id","learner_id","idea_id","problem_id","problem_version",
                  "dimension","score","session_id","submitted_at","response_json",
                  "evidence_ref","rubric_version","delayed","transfer"))
                same = oldrow == row
                if "submitted_at" not in event:
                    same = oldrow[:8] + oldrow[9:] == row[:8] + row[9:]
                if not same:
                    raise LearnerEventConflict("attempt_id reused with different event content")
                return {"attempt_id":attempt,"state":"duplicate","estimate":
                        self.estimate(learner,idea,dimension).__dict__}
            db.execute("""INSERT INTO learner_attempts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",row)
        return {"attempt_id":attempt,"state":"recorded",
                "estimate":self.estimate(learner,idea,dimension).__dict__}

    def estimate(self, learner_id: str, idea_id: str, dimension: str) -> SkillEstimate:
        if dimension not in DIMENSIONS:
            raise ValueError("unsupported learner evidence dimension")
        with self._connect() as db:
            rows=db.execute("""SELECT score,session_id,delayed,transfer
              FROM learner_attempts WHERE learner_id=? AND idea_id=? AND dimension=?
              ORDER BY submitted_at""",(learner_id,idea_id,dimension)).fetchall()
        # Uniform Beta(1,1) prior. Fractional rubric scores contribute soft evidence.
        successes=sum(float(r["score"]) for r in rows)
        failures=sum(1-float(r["score"]) for r in rows)
        alpha,beta=1+successes,1+failures
        mean=alpha/(alpha+beta)
        uncertainty=(alpha*beta/(((alpha+beta)**2)*(alpha+beta+1)))**0.5
        sessions=len({r["session_id"] for r in rows})
        delayed=any(r["delayed"] for r in rows)
        transfer=any(r["transfer"] for r in rows)
        state=("unobserved" if not rows else "emerging")
        if len(rows)>=2 and sessions>=2 and mean>=0.75:
            state="retained" if delayed and transfer else "provisionally_mastered"
        elif len(rows)>=1:
            state="practicing" if mean<0.8 else "emerging"
        return SkillEstimate(idea_id,dimension,mean,uncertainty,len(rows),sessions,state)

    def attempts(self, learner_id: str, idea_id: str | None=None) -> list[dict[str,Any]]:
        with self._connect() as db:
            if idea_id:
                rows=db.execute("SELECT * FROM learner_attempts WHERE learner_id=? AND idea_id=? ORDER BY submitted_at",
                                (learner_id,idea_id)).fetchall()
            else:
                rows=db.execute("SELECT * FROM learner_attempts WHERE learner_id=? ORDER BY submitted_at",
                                (learner_id,)).fetchall()
        result=[]
        for row in rows:
            item=dict(row); item["response"]=json.loads(item.pop("response_json"))
            result.append(item)
        return result


def select_next_lesson(learner_id: str, store: LearnerStore,
                       idea_graph: Mapping[str,Any],
                       lesson_catalog: list[Mapping[str,Any]],
                       curriculum_id: str | None = None) -> dict[str,Any]:
    """Select an evidence-grounded lesson; never infer mastery from missing data."""
    if not isinstance(idea_graph,Mapping) or not isinstance(lesson_catalog,list):
        raise ValueError("idea graph and lesson catalog are required")
    estimates={}
    for idea_id,idea in idea_graph.items():
        dims=idea.get("dimensions",["conceptual_explanation","procedure"])
        estimates[idea_id]={d:store.estimate(learner_id,idea_id,d) for d in dims}
    candidates=[]
    for lesson in lesson_catalog:
        if curriculum_id is not None and lesson.get("curriculum_id") != curriculum_id:
            continue
        lesson_id=lesson.get("lesson_id")
        idea_id=lesson.get("idea_id")
        if not isinstance(lesson_id,str) or idea_id not in idea_graph:
            continue
        prerequisites=idea_graph[idea_id].get("prerequisites",[])
        prereq_states=[]
        for p in prerequisites:
            if p not in idea_graph:
                prereq_states.append("unknown")
            else:
                p_dims=idea_graph[p].get("dimensions",["conceptual_explanation"])
                p_est=[store.estimate(learner_id,p,d) for d in p_dims]
                prereq_states.append("ready" if p_est and all(x.state in
                    {"provisionally_mastered","retained"} for x in p_est) else "needs_practice")
        target_dims=idea_graph[idea_id].get("dimensions",["conceptual_explanation","procedure"])
        target=[store.estimate(learner_id,idea_id,d) for d in target_dims]
        unobserved=sum(x.state=="unobserved" for x in target)
        weak=sum(x.mean<0.75 for x in target if x.observations)
        uncertain=sum(x.uncertainty for x in target)
        # Do not recommend a lesson whose declared prerequisites are not demonstrated.
        if any(state != "ready" for state in prereq_states):
            continue
        # Favor unobserved/weak target skills and uncertainty reduction.
        score=2.0*unobserved+1.5*weak+uncertain
        candidates.append((score,lesson_id,idea_id,prereq_states,target))
    if not candidates:
        return {"state":"no_candidate","learner_id":learner_id}
    candidates.sort(key=lambda x:(-x[0],x[1]))
    score,lesson_id,idea_id,prereqs,target=candidates[0]
    return {"state":"recommended","learner_id":learner_id,"lesson_id":lesson_id,
      "idea_id":idea_id,"score":round(score,4),
      "reason":{"prerequisites":prereqs,
        "target_skills":{x.dimension:{"state":x.state,"mean":round(x.mean,4),
          "uncertainty":round(x.uncertainty,4),"observations":x.observations}
          for x in target}},
      "authority":"recommendation_only"}


def hermes_learning_handler(store: LearnerStore, graph: Mapping[str,Any],
                            lessons: list[Mapping[str,Any]]):
    """Injectable Hermes outbox handler for learner attempts and lesson requests."""
    def handle(event: Mapping[str,Any]) -> Mapping[str,Any]:
        topic=event.get("topic")
        payload=event.get("payload",{})
        if topic==ATTEMPT_TOPIC:
            result=store.record_attempt(payload)
            return {"kind":"learner.attempt.recorded",**result}
        if topic=="merlin.learning.recommendation":
            learner=payload.get("learner_id")
            LearnerStore._required(learner,"learner_id")
            curriculum_id=payload.get("curriculum_id")
            return {"kind":"learner.lesson.recommended",
                    **select_next_lesson(learner,store,graph,lessons,
                                         curriculum_id=curriculum_id)}
        raise ValueError("unsupported learning event topic")
    return handle


class HermesLearningRouter:
    """Route durable learner events through Hermes' existing leased outbox protocol."""
    def __init__(self, outbox: Any, store: LearnerStore,
                 graph: Mapping[str,Any], lessons: list[Mapping[str,Any]],
                 worker_id: str = "hermes-learning"):
        from .hermes_outbox import HermesOutboxConsumer
        self.consumer=HermesOutboxConsumer(outbox)
        self.handler=hermes_learning_handler(store,graph,lessons)
        self.worker_id=worker_id

    def run_once(self) -> dict[str,Any] | None:
        return self.consumer.consume_one(
            self.worker_id, self.handler,
            topics=(ATTEMPT_TOPIC,"merlin.learning.recommendation"),
            lease_seconds=30,retry_delay_seconds=2,max_attempts=3)
