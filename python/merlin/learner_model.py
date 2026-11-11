"""Persistent, evidence-based learner model and Hermes lesson selection.

This is a local SQLite reference service. Attempts are append-only and
idempotent; estimates are transparent Beta-binomial summaries, not diagnoses.
"""
from __future__ import annotations
from dataclasses import dataclass
from contextlib import closing
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
    "artistic_composition", "observation_accuracy", "material_technique",
    "visual_analysis", "artistic_critique", "artistic_intent", "revision",
    "cultural_context", "creative_iteration", "authorship_provenance",
    "construction", "classification", "artistic_variation", "spatial_reasoning", "visualization", "scaling_analysis", "modeling", "interpretation", "algorithm_design", "parameter_reasoning", "reproducibility", "data_reasoning", "visual_encoding", "uncertainty", "critical_interpretation", "negative_space", "proportion", "composition", "balance", "rhythm", "contrast", "intentional_choice", "tool_control", "material_experiment", "craft_precision", "motif_design", "repeat_structure", "variation", "visual_coherence", "source_attribution", "contextual_interpretation", "ethical_representation", "spatial_composition", "viewpoint", "material_constraints", "material_selection", "structural_iteration", "fabrication_accuracy", "temporal_rhythm", "motion_design", "sequence", "sound_light_mapping", "artist_statement", "critique", "audience_awareness", "rule_design", "parameter_exploration", "creative_control", "iteration", "data_selection", "uncertainty_disclosure", "interpretive_integrity", "authorship_disclosure", "source_provenance", "licensing_awareness", "model_critique", "question_formulation", "literature_context", "artifact_iteration", "research_notebook", "formal_analysis", "revision_rationale", "self_reflection", "curation", "communication", "evidence_presentation", "limitations",
}
PATHWAYS = frozenset({"mathematician", "mathematics_programmer", "computational_hacker"})
EXPLANATION_MODES = frozenset({"visual", "worked_example", "socratic", "historical", "textual", "video", "interactive", "code"})
PACE_MAX_MINUTES = {"gentle": 20, "standard": 35, "intensive": 60, "adaptive": None}
DEFAULT_LEARNER_PROFILE = {
    "schema_version": 1,
    "pathway_weights": {
        "mathematician": 1 / 3,
        "mathematics_programmer": 1 / 3,
        "computational_hacker": 1 / 3,
    },
    "interests": [],
    "explanation_modes": ["worked_example", "visual", "socratic"],
    "pace": "adaptive",
    "max_minutes": None,
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
        with closing(self._connect()) as db:
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
            CREATE TABLE IF NOT EXISTS learner_profiles(
              learner_id TEXT PRIMARY KEY,
              profile_json TEXT NOT NULL,
              updated_at REAL NOT NULL);
            """)
    
    def _connect(self):
        db=sqlite3.connect(self.path,timeout=30)
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def get_profile(self, learner_id: str) -> dict[str, Any]:
        """Return persisted learner preferences or a safe, balanced default."""
        learner = self._required(learner_id, "learner_id")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT profile_json,updated_at FROM learner_profiles WHERE learner_id=?",
                (learner,),
            ).fetchone()
        if row is None:
            return {**json.loads(json.dumps(DEFAULT_LEARNER_PROFILE)), "updated_at": None}
        try:
            profile = json.loads(row["profile_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("stored learner profile is invalid") from exc
        if not isinstance(profile, dict) or profile.get("schema_version") != 1:
            raise ValueError("stored learner profile has an unsupported schema")
        return {**profile, "updated_at": row["updated_at"]}

    def update_profile(self, learner_id: str, updates: Mapping[str, Any]) -> dict[str, Any]:
        """Persist learner-controlled preferences in the existing evidence database."""
        learner = self._required(learner_id, "learner_id")
        if not isinstance(updates, Mapping):
            raise ValueError("profile updates must be an object")
        allowed = {"pathway_weights", "interests", "explanation_modes", "pace", "max_minutes"}
        unknown = set(updates) - allowed
        if unknown:
            raise ValueError(f"unsupported learner profile fields: {sorted(unknown)}")
        current = self.get_profile(learner)
        profile = {key: current[key] for key in DEFAULT_LEARNER_PROFILE}

        if "pathway_weights" in updates:
            raw = updates["pathway_weights"]
            if not isinstance(raw, Mapping) or not raw:
                raise ValueError("pathway_weights must be a non-empty object")
            unknown_paths = set(raw) - PATHWAYS
            if unknown_paths:
                raise ValueError(f"unsupported learning pathways: {sorted(str(path) for path in unknown_paths)}")
            weights = dict(profile["pathway_weights"])
            for path, value in raw.items():
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                    raise ValueError(f"pathway weight for {path} must be between zero and one")
                weights[path] = float(value)
            total = sum(weights.values())
            if total <= 0:
                raise ValueError("at least one pathway weight must be greater than zero")
            profile["pathway_weights"] = {
                path: round(value / total, 8) for path, value in weights.items()
            }

        if "interests" in updates:
            raw_interests = updates["interests"]
            if not isinstance(raw_interests, list) or len(raw_interests) > 30:
                raise ValueError("interests must be a list of at most 30 strings")
            normalized = []
            for value in raw_interests:
                if not isinstance(value, str) or not value.strip() or len(value.strip()) > 64:
                    raise ValueError("each interest must be a non-empty string of at most 64 characters")
                tag = value.strip().lower().replace(" ", "_")
                if tag not in normalized:
                    normalized.append(tag)
            profile["interests"] = normalized

        if "explanation_modes" in updates:
            modes = updates["explanation_modes"]
            if not isinstance(modes, list) or not modes or any(
                not isinstance(mode, str) or mode not in EXPLANATION_MODES for mode in modes
            ):
                raise ValueError("explanation_modes must contain supported modes")
            if len(set(modes)) != len(modes):
                raise ValueError("explanation_modes must be unique")
            profile["explanation_modes"] = modes

        if "pace" in updates:
            pace = updates["pace"]
            if not isinstance(pace, str) or pace not in PACE_MAX_MINUTES:
                raise ValueError("pace must be gentle, standard, intensive, or adaptive")
            profile["pace"] = pace
            if "max_minutes" not in updates:
                profile["max_minutes"] = PACE_MAX_MINUTES[pace]

        if "max_minutes" in updates:
            minutes = updates["max_minutes"]
            if minutes is not None and (
                isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= 180
            ):
                raise ValueError("max_minutes must be null or an integer from 1 to 180")
            profile["max_minutes"] = minutes

        encoded = json.dumps(profile, sort_keys=True, ensure_ascii=False, allow_nan=False)
        updated_at = time.time()
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                """INSERT INTO learner_profiles(learner_id,profile_json,updated_at)
                   VALUES(?,?,?) ON CONFLICT(learner_id) DO UPDATE SET
                   profile_json=excluded.profile_json,updated_at=excluded.updated_at""",
                (learner, encoded, updated_at),
            )
        return {**profile, "updated_at": updated_at}

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
        with closing(self._connect()) as db, db:
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
        with closing(self._connect()) as db, db:
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
        with closing(self._connect()) as db, db:
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


def select_next_lesson(
    learner_id: str,
    store: LearnerStore,
    idea_graph: Mapping[str, Any],
    lesson_catalog: list[Mapping[str, Any]],
    curriculum_id: str | None = None,
    *,
    path_weights: Mapping[str, float] | None = None,
    interests: list[str] | tuple[str, ...] = (),
    max_minutes: int | None = None,
    completed_lesson_ids: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    """Select an evidence-grounded lesson using mastery and learner preferences.

    Path and interest preferences only rank/filter pedagogical recommendations;
    they never change evidence, mastery, or proof status.
    """
    if not isinstance(idea_graph, Mapping) or not isinstance(lesson_catalog, list):
        raise ValueError("idea graph and lesson catalog are required")
    normalized_paths: dict[str, float] | None = None
    if path_weights is not None:
        if not isinstance(path_weights, Mapping) or not path_weights:
            raise ValueError("path_weights must be a non-empty mapping")
        unknown = set(path_weights) - PATHWAYS
        if unknown:
            raise ValueError(f"unsupported learning pathways: {sorted(str(path) for path in unknown)}")
        normalized_paths = {}
        for path, value in path_weights.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"pathway weight for {path} must be between zero and one")
            normalized_paths[path] = float(value)
        total = sum(normalized_paths.values())
        if total <= 0:
            raise ValueError("at least one pathway weight must be greater than zero")
        normalized_paths = {path: value / total for path, value in normalized_paths.items()}

    if isinstance(interests, str) or not isinstance(interests, (list, tuple)):
        raise ValueError("interests must be a list or tuple of strings")
    if any(not isinstance(tag, str) or not tag.strip() for tag in interests):
        raise ValueError("interests must contain non-empty strings")
    interest_set = {tag.strip().lower().replace(" ", "_") for tag in interests}

    if max_minutes is not None and (
        isinstance(max_minutes, bool) or not isinstance(max_minutes, int) or not 1 <= max_minutes <= 180
    ):
        raise ValueError("max_minutes must be an integer from 1 to 180")
    if isinstance(completed_lesson_ids, str) or not isinstance(completed_lesson_ids, (list, tuple)):
        raise ValueError("completed_lesson_ids must be a list or tuple")
    if any(not isinstance(item, str) or not item for item in completed_lesson_ids):
        raise ValueError("completed_lesson_ids must contain non-empty strings")
    completed = set(completed_lesson_ids)

    ranked: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for lesson in lesson_catalog:
        if not isinstance(lesson, Mapping):
            raise ValueError("lesson catalog entries must be objects")
        if curriculum_id is not None and lesson.get("curriculum_id") != curriculum_id:
            continue
        lesson_id = lesson.get("lesson_id")
        idea_id = lesson.get("idea_id")
        if not isinstance(lesson_id, str) or not lesson_id or idea_id not in idea_graph:
            continue
        if lesson_id in completed:
            continue

        minutes = lesson.get("estimated_minutes", 20)
        if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 1:
            raise ValueError(f"{lesson_id}: estimated_minutes must be a positive integer")
        if max_minutes is not None and minutes > max_minutes:
            blocked.append({"lesson_id": lesson_id, "blocked_reason": "exceeds_time_budget",
                            "estimated_minutes": minutes})
            continue

        lesson_paths = lesson.get("pathways", lesson.get("path_tags", []))
        if not isinstance(lesson_paths, (list, tuple)) or any(
            not isinstance(path, str) or path not in PATHWAYS for path in lesson_paths
        ):
            raise ValueError(f"{lesson_id}: pathways must contain supported path IDs")
        if normalized_paths is None or not lesson_paths:
            pathway_fit = 1.0
        else:
            pathway_fit = sum(weight for path, weight in normalized_paths.items() if path in lesson_paths)
            if pathway_fit <= 0:
                blocked.append({"lesson_id": lesson_id, "blocked_reason": "pathway_not_selected"})
                continue

        lesson_interests = lesson.get("interest_tags", [])
        if not isinstance(lesson_interests, (list, tuple)) or any(
            not isinstance(tag, str) or not tag for tag in lesson_interests
        ):
            raise ValueError(f"{lesson_id}: interest_tags must be strings")
        interest_fit = (
            len(interest_set.intersection(lesson_interests)) / len(lesson_interests)
            if lesson_interests else 0.0
        )

        prerequisites = idea_graph[idea_id].get("prerequisites", [])
        if not isinstance(prerequisites, list):
            raise ValueError(f"{idea_id}: prerequisites must be a list")
        prereq_states = []
        missing_prerequisites = []
        for prerequisite in prerequisites:
            if prerequisite not in idea_graph:
                prereq_states.append("unknown")
                missing_prerequisites.append(prerequisite)
                continue
            prerequisite_dimensions = idea_graph[prerequisite].get(
                "dimensions", ["conceptual_explanation"]
            )
            prerequisite_estimates = [
                store.estimate(learner_id, prerequisite, dimension)
                for dimension in prerequisite_dimensions
            ]
            ready = bool(prerequisite_estimates) and all(
                estimate.state in {"provisionally_mastered", "retained"}
                for estimate in prerequisite_estimates
            )
            prereq_states.append("ready" if ready else "needs_practice")
            if not ready:
                missing_prerequisites.append(prerequisite)
        if missing_prerequisites:
            blocked.append({
                "lesson_id": lesson_id,
                "blocked_reason": "prerequisites_not_yet_demonstrated",
                "missing_prerequisites": sorted(missing_prerequisites),
            })
            continue

        target_dimensions = idea_graph[idea_id].get(
            "dimensions", ["conceptual_explanation", "procedure"]
        )
        target = [
            store.estimate(learner_id, idea_id, dimension)
            for dimension in target_dimensions
        ]
        unobserved = sum(estimate.state == "unobserved" for estimate in target)
        weak = sum(estimate.mean < 0.75 for estimate in target if estimate.observations)
        uncertainty = sum(estimate.uncertainty for estimate in target)
        mastery_gap_score = 2.0 * unobserved + 1.5 * weak + uncertainty

        learning_value = lesson.get("learning_value", 0.5)
        transfer_value = lesson.get("transfer_value", 0.5)
        for label, value in (("learning_value", learning_value), ("transfer_value", transfer_value)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{lesson_id}: {label} must be between zero and one")
        time_fit = 0.5 if max_minutes is None else max(0.0, 1.0 - minutes / max_minutes)
        score = (
            mastery_gap_score
            + 1.0 * pathway_fit
            + 0.75 * interest_fit
            + 0.25 * learning_value
            + 0.25 * transfer_value
            + 0.10 * time_fit
        )
        components = {
            "mastery_gap": round(mastery_gap_score, 6),
            "pathway_fit": round(pathway_fit, 6),
            "interest_fit": round(interest_fit, 6),
            "learning_value": round(float(learning_value), 6),
            "transfer_value": round(float(transfer_value), 6),
            "time_fit": round(time_fit, 6),
        }
        reasons = []
        if pathway_fit > 0:
            reasons.append("matches_selected_learning_paths")
        if interest_fit > 0:
            reasons.append("matches_learner_interests")
        if unobserved or weak:
            reasons.append("addresses_unsettled_skills")
        if transfer_value >= 0.8:
            reasons.append("supports_transfer")
        if max_minutes is not None:
            reasons.append("fits_time_budget")
        ranked.append({
            "lesson_id": lesson_id,
            "idea_id": idea_id,
            "score": round(score, 6),
            "score_components": components,
            "reason_codes": reasons,
            "reason": {
                "prerequisites": prereq_states,
                "target_skills": {
                    estimate.dimension: {
                        "state": estimate.state,
                        "mean": round(estimate.mean, 4),
                        "uncertainty": round(estimate.uncertainty, 4),
                        "observations": estimate.observations,
                    }
                    for estimate in target
                },
            },
            "estimated_minutes": minutes,
        })

    ranked.sort(key=lambda item: (-item["score"], item["lesson_id"]))
    blocked.sort(key=lambda item: (item["lesson_id"], item["blocked_reason"]))
    if not ranked:
        return {
            "state": "no_candidate",
            "learner_id": learner_id,
            "blocked_lessons": blocked,
            "authority": "recommendation_only",
        }
    selected = ranked[0]
    return {
        "state": "recommended",
        "learner_id": learner_id,
        **selected,
        "blocked_lessons": blocked,
        "authority": "recommendation_only",
    }


def hermes_learning_handler(store: LearnerStore, graph: Mapping[str,Any],
                            lessons: list[Mapping[str,Any]]):
    """Injectable Hermes outbox handler for learner attempts and lesson requests."""
    def handle(event: Mapping[str,Any]) -> Mapping[str,Any]:
        topic=event.get("topic")
        payload=event.get("payload",{})
        if topic==ATTEMPT_TOPIC:
            scored=score_attempt_event(payload)
            result=store.record_attempt(scored)
            return {"kind":"learner.attempt.recorded",**result}
        if topic=="merlin.learning.recommendation":
            learner=payload.get("learner_id")
            LearnerStore._required(learner,"learner_id")
            curriculum_id=payload.get("curriculum_id")
            profile = store.get_profile(learner)
            return {"kind":"learner.lesson.recommended",
                    **select_next_lesson(
                        learner, store, graph, lessons,
                        curriculum_id=curriculum_id,
                        path_weights=profile["pathway_weights"],
                        interests=profile["interests"],
                        max_minutes=profile["max_minutes"],
                    )}
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


# Server-owned scoring contracts. Browser-supplied scores are never trusted by the API.
SCORING_RUBRICS = {
    "rotor-half-angle": {
        "idea_id": "MATH-ALG-001", "dimension": "recognition",
        "rubric_version": "rotation-rubric-0.1",
    },
    "rotation-coordinate-90": {
        "idea_id": "MATH-REP-001", "dimension": "procedure",
        "rubric_version": "rotation-coordinate-rubric-0.1",
    },
    "invoice-approval-boundary": {
        "idea_id": "B2B-AI-001", "dimension": "recognition",
        "rubric_version": "b2b-agentic-r1",
    },
    "b2b-precision-recall": {
        "idea_id": "B2B-ML-001", "dimension": "procedure",
        "rubric_version": "b2b-metrics-r1",
    },
    "radial-symmetry-step-angle": {
        "idea_id": "MATH-ART-001", "dimension": "recognition",
        "rubric_version": "math-recognition-r1",
    },
    "radial-pattern-composition": {
        "idea_id": "ART-PAT-001", "dimension": "self_reflection",
        "rubric_version": "reflection-completion-r1",
    },
}


def score_attempt_event(event: Mapping[str,Any]) -> dict[str,Any]:
    """Apply a server-owned objective rubric; ignore client score/idea/dimension claims."""
    if not isinstance(event,Mapping):
        raise ValueError("attempt event must be an object")
    problem_id=LearnerStore._required(event.get("problem_id"),"problem_id")
    rubric=SCORING_RUBRICS.get(problem_id)
    if rubric is None:
        raise ValueError("no server scoring rubric is registered for this problem")
    response=event.get("response",{})
    if not isinstance(response,Mapping):
        raise ValueError("response must be an object")
    if problem_id=="rotor-half-angle":
        score=1.0 if response.get("selected_option")=="a" else 0.0
    elif problem_id=="rotation-coordinate-90":
        try:
            x,y=float(response.get("x")),float(response.get("y"))
            score=1.0 if math.isfinite(x) and math.isfinite(y) and abs(x)<=0.01 and abs(y-1)<=0.01 else 0.0
        except (TypeError,ValueError):
            score=0.0
    elif problem_id=="invoice-approval-boundary":
        score=1.0 if response.get("choice")=="b" else 0.0
    elif problem_id=="radial-symmetry-step-angle":
        try:
            n=int(response.get("n"))
            answer=float(response.get("answer"))
            score=1.0 if 3<=n<=16 and math.isfinite(answer) and abs(answer-360.0/n)<1e-9 else 0.0
        except (TypeError,ValueError,OverflowError):
            score=0.0
    elif problem_id=="radial-pattern-composition":
        reflection=response.get("reflection")
        score=1.0 if isinstance(reflection,str) and len(reflection.strip())>=20 else 0.0
    else:
        try:
            precision=float(response.get("precision_percent"))
            recall=float(response.get("recall_percent"))
            score=1.0 if (math.isfinite(precision) and math.isfinite(recall)
                          and abs(precision-80.0)<=0.5
                          and abs(recall-88.8888889)<=0.5) else 0.0
        except (TypeError,ValueError):
            score=0.0
    return {**dict(event), "idea_id":rubric["idea_id"],
            "dimension":rubric["dimension"], "score":score,
            "rubric_version":rubric["rubric_version"],
            "scoring_source":"server_rubric"}
