"""Loopback-only Merlin MVP API.

Provides deterministic research/engineering contracts and an append-only
metadata event ledger. Model, image and video generation are reported as
unconfigured until a real adapter is connected.
"""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import closing
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import signal
from threading import Event, Thread
import hmac
from pathlib import Path
import sqlite3
from typing import Any
from urllib.parse import urlparse, urlsplit, parse_qs, unquote
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from time import perf_counter

from .council import PERSONAS, build_deliberation_packets
from .council_runtime import run_local_council
from .simulation import MerlinSimulation
from .telemetry import normalize_event, telemetry_view, record_runtime_event
from .telemetry_graph import build_telemetry_graph
from .learner_model import LearnerStore, select_next_lesson, HermesLearningRouter, score_attempt_event
from .event_outbox import MerlinEventOutbox, LeaseConflict
from .intent_compiler import Asset, IntentSpec, ContinuityState, compile_directive
from .math_transfer import preview_transfers
from .interaction_learning import InteractionLearningStore, analyze_interactions
from .memory_vault import MerlinMemoryVault
from .capability_registry import capability_snapshot, validate_graph
from .learning_platform import Actor as LearningActor, LearningPlatform
from .identity import learning_identity_resolver_from_environment
from .research import (
    AnalogyMap, Idea, PromotionPacket, qualify_rsi_candidate, rank_ideas,
    validate_analogy,
)
from .engineering.geometry import GeometrySpec, Point3D, validate_geometry, bounding_box
from .engineering.netlist import Component, Connection, Net, Netlist, validate_netlist
from .public_literature import PublicLiteratureSearch
from .virtual_repository import VirtualRepository, VirtualGitError
from .virtual_repository_seed import build_repository_seed

MAX_BODY = 1_000_000
MAX_PROXY_RESPONSE = 16_000_000


def _loopback_endpoint(env_name: str, default: str) -> str:
    value = os.environ.get(env_name, default)
    parsed = urlsplit(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError(f"{env_name} must be an http loopback URL")
    return value


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _append_component_event(store: EventStore, *, source: str, kind: str,
                           component: str, task_id: str, payload: dict[str, Any],
                           duration_ms: float | None = None,
                           model_id: str | None = None,
                           evidence_refs: list[str] | None = None) -> None:
    event = normalize_event({
        "source": source, "kind": kind, "run_id": sha256(_json_bytes({
            "component": component, "task": task_id, "nonce": os.urandom(16).hex()
        })).hexdigest(), "task_id": task_id, "payload": {"component": component, **payload},
        "duration_ms": duration_ms, "model_id": model_id,
        "evidence_refs": evidence_refs or [],
    })
    store.append("/api/telemetry/ingest",
                 {"event_id": event["event_id"], "source": source},
                 {"event": event})


def _remote_model_endpoint() -> tuple[str, str]:
    """Return a HTTPS endpoint pinned to a built-in or explicit custom host."""
    endpoint = os.environ.get("MERLIN_REMOTE_MODEL_URL", "").strip()
    api_key = os.environ.get("MERLIN_REMOTE_API_KEY", "").strip()
    allowed = {
        host.strip().lower()
        for host in os.environ.get("MERLIN_REMOTE_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    }
    if not endpoint or not api_key:
        raise ValueError("remote model requires an endpoint and API key")
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "https" or not parsed.hostname
        or parsed.username or parsed.password or parsed.fragment
    ):
        raise ValueError("remote model URL must use HTTPS without embedded credentials")
    hostname = parsed.hostname.lower()
    if hostname not in allowed:
        raise ValueError("custom remote model URL requires an explicitly allowlisted host")
    return endpoint, api_key


class EventStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                request_sha256 TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""")

    def append(self, kind: str, request: dict[str, Any], summary: dict[str, Any]) -> None:
        digest = sha256(_json_bytes(request)).hexdigest()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "INSERT INTO events(kind,request_sha256,summary_json,created_at) VALUES(?,?,?,?)",
                (kind, digest, json.dumps(summary, sort_keys=True), datetime.now(timezone.utc).isoformat()),
            )

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with closing(sqlite3.connect(self.path)) as db, db:
            rows = db.execute(
                "SELECT id,kind,request_sha256,summary_json,created_at FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"id": row[0], "kind": row[1], "request_sha256": row[2],
             "summary": json.loads(row[3]), "created_at": row[4]}
            for row in rows
        ]

    def by_kind(self, kind: str, limit: int = 10000) -> list[dict[str, Any]]:
        """Return oldest-first event metadata for deterministic replay."""
        if not 1 <= limit <= 100000:
            raise ValueError("event limit out of range")
        with closing(sqlite3.connect(self.path)) as db, db:
            rows = db.execute(
                "SELECT id,kind,request_sha256,summary_json,created_at FROM events WHERE kind=? ORDER BY id ASC LIMIT ?",
                (kind, limit),
            ).fetchall()
        return [{"id": row[0], "kind": row[1], "request_sha256": row[2],
                 "summary": json.loads(row[3]), "created_at": row[4]} for row in rows]



def _runtime_provider_status() -> dict[str, Any]:
    """Expose qualification state without leaking endpoint URLs or credentials."""
    local_model = os.environ.get("MERLIN_LOCAL_MODEL", os.environ.get("MERLIN_MODEL_NAME", "")).strip()
    remote_model = os.environ.get("MERLIN_REMOTE_MODEL_NAME", os.environ.get("MERLIN_MODEL_NAME", "")).strip()
    local_ready = os.environ.get("MERLIN_MODEL_QUALIFIED") == "1" and bool(local_model)
    if local_ready:
        try:
            _loopback_endpoint("MERLIN_MODEL_URL", "http://127.0.0.1:8080/v1/chat/completions")
        except ValueError:
            local_ready = False
    remote_ready = (
        os.environ.get("MERLIN_REMOTE_MODEL_QUALIFIED") == "1"
        and bool(remote_model)
        and bool(os.environ.get("MERLIN_REMOTE_MODEL_URL", "").strip())
    )
    if remote_ready:
        try:
            _remote_model_endpoint()
        except ValueError:
            remote_ready = False
    tts_ready = os.environ.get("MERLIN_TTS_QUALIFIED") == "1"
    if tts_ready:
        try:
            _loopback_endpoint("MERLIN_TTS_URL", "http://127.0.0.1:8880/v1/audio/speech")
        except ValueError:
            tts_ready = False
    return {
        "schema": "merlin-runtime-providers/1",
        "providers": {
            "local": {"status": "QUALIFIED_CONFIGURED" if local_ready else "UNAVAILABLE",
                      "health": "not_probed",
                      "model": local_model if local_ready else None,
                      "transport": "loopback OpenAI-compatible API"},
            "cloud": {"status": "QUALIFIED_CONFIGURED" if remote_ready else "UNAVAILABLE",
                      "health": "not_probed",
                      "provider": "custom" if remote_ready else None,
                      "model": remote_model if remote_ready else None,
                      "transport": "explicitly allowlisted HTTPS OpenAI-compatible API"},
            "speech_output": {"status": "QUALIFIED_CONFIGURED" if tts_ready else "UNAVAILABLE",
                              "health": "not_probed",
                              "model": os.environ.get("MERLIN_TTS_MODEL") if tts_ready else None,
                              "transport": "loopback TTS sidecar"},
            "speech_input": {"status": "BROWSER_DEPENDENT",
                             "transport": "browser SpeechRecognition API; permission required"},
        },
        "raw_conversation_retention": False,
        "provider_credentials_exposed": False,
    }


CAPABILITIES = [
    {"id": "research.math_transfer.preview", "status": "AVAILABLE", "evidence": "deterministic, provenance-aware transfer hypotheses; no automatic promotion"},
    {"id": "research.literature.search", "status": "AVAILABLE", "evidence": "zero-configuration Crossref and arXiv discovery; source-hashed documents remain unverified"},
    {"id": "forge.virtual_repository", "status": "AVAILABLE", "evidence": "SQLite content-addressed commits, branches, pull requests, three-way merge, rollback and append-only events; no external Git host required"},
    {"id": "intent.compile.preview", "status": "AVAILABLE", "evidence": "deterministic typed directive preview; optional canonical-registry artifact persistence; no external execution authority"},
    {"id": "learning.interaction.observe", "status": "AVAILABLE", "evidence": "metadata-only operational telemetry plus explicit categorical outcome feedback"},
    {"id": "learning.interaction.analyze", "status": "AVAILABLE", "evidence": "aggregate improvement proposals with minimum sample thresholds; recommendation-only"},
    {"id": "simulation.world", "status": "AVAILABLE", "evidence": "deterministic bounded world state, actions, and event telemetry"},
    {"id": "simulation.hud", "status": "AVAILABLE", "evidence": "responsive HUD renders live simulation API data"},
    {"id": "council.roles", "status": "AVAILABLE", "evidence": "deterministic simulated persona registry"},
    {"id": "council.deliberation.prepare", "status": "AVAILABLE", "evidence": "role-specific prompt packets and auditable self-map contract"},
    {"id": "council.deliberation.run_local", "status": "QUALIFICATION_GATED", "evidence": "six isolated local model openings; optional bounded cross-examination"},
    {"id": "research.ideonomy.rank", "status": "AVAILABLE", "evidence": "unit-tested deterministic candidate ranking"},
    {"id": "research.analogy.validate", "status": "AVAILABLE", "evidence": "unit-tested invariant and boundary checks"},
    {"id": "research.rsi.qualify", "status": "AVAILABLE", "evidence": "fail-closed qualification contract"},
    {"id": "learning.attempts.persist", "status": "AVAILABLE", "evidence": "append-only SQLite learner attempt ledger with idempotent event IDs"},
    {"id": "learning.mastery.estimate", "status": "AVAILABLE", "evidence": "per-idea, per-dimension Beta-binomial estimates and independent-session checks"},
    {"id": "learning.hermes.route", "status": "AVAILABLE_WITH_OUTBOX", "evidence": "learner attempt and recommendation events published to Hermes learning topics"},
    {"id": "learning.lesson.recommend", "status": "AVAILABLE", "evidence": "canonical prerequisite graph and transparent learner-evidence routing"},
    {"id": "engineering.geometry.validate", "status": "AVAILABLE", "evidence": "unit-tested structural mesh checks"},
    {"id": "engineering.geometry.openscad", "status": "AVAILABLE", "evidence": "typed geometry exporter"},
    {"id": "engineering.netlist.validate", "status": "AVAILABLE", "evidence": "unit-tested structural/rating preflight"},
    {"id": "voice.kokoro", "status": "OPTIONAL_LOCAL_SERVICE", "endpoint": "http://127.0.0.1:8880"},
    {"id": "model.remote_openai_compatible", "status": "CONFIGURED_AT_RUNTIME", "transport": "HTTPS + SSE", "credential_source": "MERLIN_REMOTE_API_KEY"},
    {"id": "model.nouscoder", "status": "NOT_QUALIFIED", "endpoint": "http://127.0.0.1:8080/v1"},
    {"id": "agent.hermes", "status": "SOURCE_DOWNLOADED_NOT_CONNECTED", "path": ".tools/hermes-agent"},
    {"id": "media.image", "status": "NOT_CONFIGURED"},
    {"id": "media.video", "status": "NOT_CONFIGURED"},
    {"id": "biology.biochemistry", "status": "NOT_CONFIGURED"},
]


def _idea(row: dict[str, Any]) -> Idea:
    return Idea(
        title=row.get("title", ""),
        mechanism=row.get("mechanism", ""),
        assumptions=tuple(row.get("assumptions", [])),
        constraints=tuple(row.get("constraints", [])),
        observable=row.get("observable", ""),
        falsifier=row.get("falsifier", ""),
        novelty=float(row.get("novelty", 0.5)),
        feasibility=float(row.get("feasibility", 0.5)),
        evidence_fit=float(row.get("evidence_fit", 0.5)),
        testability=float(row.get("testability", 0.5)),
        resource_cost=float(row.get("resource_cost", 0.5)),
        source_domains=tuple(row.get("source_domains", [])),
    )


def _analogy(data: dict[str, Any]) -> AnalogyMap:
    return AnalogyMap(
        source_problem=data.get("source_problem", ""),
        target_problem=data.get("target_problem", ""),
        entity_mapping=dict(data.get("entity_mapping", {})),
        operation_mapping=dict(data.get("operation_mapping", {})),
        required_invariants=tuple(data.get("required_invariants", [])),
        preserved_invariants=tuple(data.get("preserved_invariants", [])),
        source_boundary_conditions=tuple(data.get("source_boundary_conditions", [])),
        target_boundary_conditions=tuple(data.get("target_boundary_conditions", [])),
        known_failure_modes=tuple(data.get("known_failure_modes", [])),
    )


def _geometry(data: dict[str, Any]) -> tuple[GeometrySpec, dict[str, Any]]:
    spec = GeometrySpec(
        name=data.get("name", ""),
        unit=data.get("unit", "mm"),
        points=tuple(Point3D(**point) for point in data.get("points", [])),
        faces=tuple(tuple(face) for face in data.get("faces", [])),
        closed_solid=bool(data.get("closed_solid", False)),
    )
    issues = [issue.__dict__ for issue in validate_geometry(spec)]
    result: dict[str, Any] = {"valid": not issues, "issues": issues}
    if not issues and spec.points:
        result["bounding_box"] = bounding_box(spec)
    return spec, result


def _netlist(data: dict[str, Any]) -> Netlist:
    components = tuple(Component(
        id=row["id"], pins=tuple(row.get("pins", [])),
        pin_roles=tuple(tuple(item) for item in row.get("pin_roles", [])),
        max_voltage_v=row.get("max_voltage_v"), max_current_a=row.get("max_current_a"),
    ) for row in data.get("components", []))
    nets = tuple(Net(
        id=row["id"],
        connections=tuple(Connection(**connection) for connection in row.get("connections", [])),
        voltage_v=row.get("voltage_v"), current_a=row.get("current_a"),
    ) for row in data.get("nets", []))
    return Netlist(components=components, nets=nets)


def make_handler(store: EventStore, hud_runtime: Any | None = None,
                 learner_store: LearnerStore | None = None,
                 learning_outbox: MerlinEventOutbox | None = None,
                 canonical_registry: Any | None = None,
                 learning_platform: LearningPlatform | None = None,
                 learning_identity_resolver: Any | None = None,
                 canonical_graph: Any | None = None,
                 hermes_worker_service: Any | None = None,
                 hermes_runtime: Any | None = None):
    simulation = MerlinSimulation()
    literature_search = PublicLiteratureSearch()
    learner_store = learner_store or LearnerStore(store.path)
    learning_db = os.environ.get("MERLIN_LEARNING_DB_PATH",
        str(Path(store.path).with_name("learning.sqlite3")))
    learning_platform = learning_platform or LearningPlatform(learning_db)
    interaction_store = InteractionLearningStore(store.path)
    memory_path = os.environ.get("MERLIN_MEMORY_DB_PATH", str(Path(store.path).with_name("memory.sqlite3")))
    memory_vault = MerlinMemoryVault(memory_path)
    repo_root = Path(__file__).resolve().parents[2]
    forge = VirtualRepository(Path(store.path).with_name("merlin-forge.sqlite3"))
    seed, seed_manifest = build_repository_seed(repo_root)
    branches = {row["name"] for row in forge.branches()}
    if not branches:
        try:
            forge.initialize(seed)
        except VirtualGitError:
            if not forge.branches():
                raise
    else:
        try:
            current_manifest = forge.read_file("main", "merlin/SEED_MANIFEST.json")
        except KeyError:
            current_manifest = None
        expected_manifest = seed["merlin/SEED_MANIFEST.json"]
        if current_manifest != expected_manifest:
            bootstrap_branch = "bootstrap/runtime-source-" + seed_manifest["tree_sha256"][:12]
            if bootstrap_branch not in branches:
                try:
                    forge.create_branch(bootstrap_branch, "main")
                except VirtualGitError:
                    if not any(row["name"] == bootstrap_branch for row in forge.branches()):
                        raise
            branch_manifest = None
            try:
                branch_manifest = forge.read_file(bootstrap_branch, "merlin/SEED_MANIFEST.json")
            except KeyError:
                pass
            if branch_manifest != expected_manifest:
                entries = list(seed.items())
                for offset in range(0, len(entries), 500):
                    forge.commit(bootstrap_branch, "Import runtime source snapshot batch " +
                                 str(offset // 500 + 1),
                                 dict(entries[offset:offset + 500]))
            existing_pr = next((row for row in forge.pull_requests("open")
                                if row["source_branch"] == bootstrap_branch
                                and row["target_branch"] == "main"), None)
            if existing_pr is None:
                forge.open_pull_request(bootstrap_branch, "main",
                    "Import verified runtime source snapshot " + seed_manifest["tree_sha256"][:12])
    catalog_path = Path(os.environ.get("MERLIN_MATH_IDEA_CATALOG",
        str(repo_root / "docs" / "research" / "merlin-mathematical-idea-catalog.v1.json")))
    learning_graph: dict[str, Any] = {}
    learning_lessons: list[dict[str, Any]] = []
    if catalog_path.is_file():
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        for idea in catalog.get("ideas", []):
            learning = idea.get("learning")
            if not isinstance(learning, dict):
                continue
            idea_id = idea.get("id")
            lesson_id = learning.get("lesson_id")
            dimensions = learning.get("dimensions", [])
            prerequisites = learning.get("prerequisites", [])
            if not isinstance(idea_id, str) or not isinstance(lesson_id, str):
                continue
            learning_graph[idea_id] = {"prerequisites": prerequisites, "dimensions": dimensions}
            art_math_ids = {"MATH-ART-001", "MATH-TESS-001", "MATH-PROJ-001",
                            "MATH-POLY-001", "MATH-PARA-001", "MATH-FRACT-002",
                            "MATH-SIG-001", "MATH-GEN-001", "MATH-DATA-001"}
            learning_lessons.append({"lesson_id": lesson_id, "idea_id": idea_id,
                                     "curriculum_id": "art-math-studio" if idea_id in art_math_ids else "mathematics"})
    # B2B competencies are a separate, versioned curriculum graph.
    b2b_graph_path = repo_root / "docs" / "merlin" / "MERLIN_B2B_LEARNING_GRAPH_V0_1.json"
    if b2b_graph_path.is_file():
        b2b_graph = json.loads(b2b_graph_path.read_text(encoding="utf-8"))
        for node in b2b_graph.get("nodes", []):
            idea_id, lesson_id = node.get("idea_id"), node.get("lesson_id")
            if not isinstance(idea_id, str) or not isinstance(lesson_id, str):
                continue
            learning_graph[idea_id] = {"prerequisites": node.get("prerequisites", []),
                                       "dimensions": node.get("dimensions", [])}
            learning_lessons.append({"lesson_id": lesson_id, "idea_id": idea_id,
                                     "curriculum_id": b2b_graph.get("curriculum_id")})
    # Artistic competencies are a separate graph, linked to math ideas by explicit curriculum mappings.
    art_graph_path = repo_root / "docs" / "merlin" / "MERLIN_ART_SKILL_GRAPH_V0_1.json"
    if art_graph_path.is_file():
        art_graph = json.loads(art_graph_path.read_text(encoding="utf-8"))
        for skill in art_graph.get("skills", []):
            skill_id = skill.get("id")
            dimensions = skill.get("dimensions", [])
            if not isinstance(skill_id, str) or not isinstance(dimensions, list):
                continue
            learning_graph[skill_id] = {"prerequisites": skill.get("prerequisites", []),
                                        "dimensions": dimensions}
            lesson_id = skill.get("lesson_id")
            if isinstance(lesson_id, str):
                learning_lessons.append({"lesson_id": lesson_id, "idea_id": skill_id,
                                         "curriculum_id": "art-math-studio"})
    learning_router = HermesLearningRouter(learning_outbox, learner_store, learning_graph,
                                           learning_lessons) if learning_outbox is not None else None
    # Worker credentials are server-side only. Each worker receives its own
    # high-entropy token and an immutable worker identity from this map.
    try:
        configured_worker_tokens = json.loads(os.environ.get("MERLIN_WORKER_TOKENS", "{}"))
        worker_tokens = {
            key: value for key, value in configured_worker_tokens.items()
            if isinstance(key, str) and key and len(key) <= 100
            and isinstance(value, str) and value.isascii() and len(value) >= 32
        } if isinstance(configured_worker_tokens, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        worker_tokens = {}
    # Generic HTTP workers receive explicit per-worker topic grants. The
    # Hermes task topic is intentionally excluded: only HermesWorker performs
    # approval/MCFC-lease revalidation before executing those tasks.
    try:
        configured_topic_allowlist = json.loads(
            os.environ.get("MERLIN_WORKER_TOPIC_ALLOWLIST", "{}"))
        worker_topic_allowlist = {}
        if isinstance(configured_topic_allowlist, dict):
            for worker_id, topics in configured_topic_allowlist.items():
                if (isinstance(worker_id, str) and worker_id in worker_tokens
                        and isinstance(topics, list) and len(topics) <= 50
                        and all(isinstance(topic, str) and topic and len(topic) <= 200
                                and topic != "merlin.hermes.task" for topic in topics)):
                    worker_topic_allowlist[worker_id] = frozenset(topics)
    except (TypeError, ValueError, json.JSONDecodeError):
        worker_topic_allowlist = {}
    configured_admin_token = os.environ.get("MERLIN_OUTBOX_ADMIN_TOKEN", "")
    admin_token = (configured_admin_token if isinstance(configured_admin_token, str)
                   and configured_admin_token.isascii() and len(configured_admin_token) >= 32
                   else "")

    def current_interaction_analysis():
        preferences = interaction_store.preferences()
        telemetry_rows = store.by_kind("/api/telemetry/ingest", 100000) if preferences["aggregate_telemetry"] else []
        telemetry_events = [row["summary"]["event"] for row in telemetry_rows
            if isinstance(row.get("summary"), dict)
            and isinstance(row["summary"].get("event"), dict)]
        feedback = interaction_store.feedback_summary()["events"] if preferences["explicit_feedback_learning"] else []
        return analyze_interactions(telemetry_events, feedback)

    # Rebuild simulation state from the durable action ledger on process restart.
    replay_rows = store.by_kind("/api/sim/step")
    replayed = 0
    for row in replay_rows:
        action = row.get("summary", {}).get("last_action")
        if isinstance(action, str):
            simulation.step(action)
            replayed += 1
    class Handler(BaseHTTPRequestHandler):
        server_version = "MerlinMVP/0.3"

        def _record_boundary(self, status: int, response_bytes: int) -> None:
            started = getattr(self, "_request_started", None)
            if started is None:
                return
            try:
                if interaction_store.preferences()["aggregate_telemetry"]:
                    record_runtime_event(store, path=urlparse(self.path).path,
                        method=self.command, status=status,
                        duration_ms=(perf_counter() - started) * 1000.0,
                        response_bytes=response_bytes)
            except Exception:
                # Observability must never change the underlying API result.
                return

        def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
            self._record_boundary(status, len(body))
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            body = _json_bytes(payload)
            self._record_boundary(status, len(body))
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _origin_allowed(self) -> bool:
            """Block cross-site browser writes to the loopback API; allow CLI clients without Origin."""
            origin = self.headers.get("Origin")
            if not origin:
                return True
            try:
                parsed_origin = urlsplit(origin)
                return (
                    parsed_origin.scheme == "http"
                    and parsed_origin.hostname in {"127.0.0.1", "localhost", "::1"}
                    and parsed_origin.port == int(self.server.server_address[1])
                    and parsed_origin.username is None
                    and parsed_origin.password is None
                )
            except (TypeError, ValueError):
                return False

        def _learning_actor(self):
            # Resolver must validate a signed session/token and return server-derived
            # identity, tenant and role. Never trust role/tenant headers or JSON fields.
            if learning_identity_resolver is None:
                return None
            actor = learning_identity_resolver(self.headers)
            return actor if isinstance(actor, LearningActor) else None

        def _worker_actor(self):
            worker_id = self.headers.get("X-Merlin-Worker-ID", "")
            authorization = self.headers.get("Authorization", "")
            if not worker_id or worker_id not in worker_tokens or not authorization.startswith("Bearer "):
                return None
            supplied = authorization[7:].strip()
            expected = worker_tokens.get(worker_id, "")
            if not supplied or not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
                return None
            return worker_id

        def _outbox_admin_authenticated(self):
            authorization = self.headers.get("Authorization", "")
            if not admin_token or not authorization.startswith("Bearer "):
                return False
            supplied = authorization[7:].strip()
            return bool(supplied) and hmac.compare_digest(
                supplied.encode("utf-8"), admin_token.encode("utf-8"))

        def do_GET(self) -> None:
            self._request_started = perf_counter()
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/api/forge/status":
                self._send(200, {"schema": "merlin-forge-status/1",
                    "storage": "sqlite_content_addressed",
                    "execution_mode": "virtual_git_with_leased_ci_queue_no_executor",
                    "branches": forge.branches(),
                    "open_pull_requests": forge.pull_requests("open"),
                    "required_checks": {"main": forge.required_checks("main")},
                    "recent_events": forge.events(30),
                    "virtual_job_counts": forge.job_counts(),
                    "runner_execution": "not_performed",
                    "promotion_authorized": False})
                return
            if path == "/api/forge/branches":
                self._send(200, {"schema": "merlin-forge-branches/1",
                                 "branches": forge.branches()})
                return
            if path == "/api/forge/pulls":
                self._send(200, {"schema": "merlin-forge-pull-requests/1",
                                 "pull_requests": forge.pull_requests()})
                return
            if path == "/api/forge/jobs":
                self._send(200, {"schema": "merlin-forge-jobs/1",
                                 "jobs": forge.jobs(limit=100)})
                return
            if path.startswith("/api/forge/jobs/") and path.endswith("/log"):
                parts = path.strip("/").split("/")
                if len(parts) != 5:
                    self._send(400, {"error": "invalid_virtual_job_log_path"})
                    return
                content = forge.read_job_log(unquote(parts[3]))
                self._send(200, {"schema": "merlin-forge-job-log/1",
                    "job_id": unquote(parts[3]), "log_utf8": content.decode("utf-8"),
                    "sha256": sha256(content).hexdigest()})
                return
            if path.startswith("/api/forge/jobs/"):
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    self._send(400, {"error": "invalid_virtual_job_path"})
                    return
                job_id = unquote(parts[3])
                self._send(200, {"schema": "merlin-forge-job/1", "job": forge.get_job(job_id)})
                return
            if path.startswith("/api/forge/checks/") and path.endswith("/log"):
                parts = path.strip("/").split("/")
                if len(parts) != 5 or not parts[3].isdigit():
                    self._send(400, {"error": "invalid_check_id"})
                    return
                content = forge.read_check_log(int(parts[3]))
                self._send(200, {"schema": "merlin-forge-check-log/1",
                    "check_id": int(parts[3]), "log_utf8": content.decode("utf-8"),
                    "sha256": sha256(content).hexdigest()})
                return
            if path == "/api/forge/checks":
                params = parse_qs(parsed.query)
                commit_id = (params.get("commit") or [""])[0]
                if not commit_id:
                    main = next((row for row in forge.branches() if row["name"] == "main"), None)
                    if main is None:
                        raise ValueError("main branch is not initialized")
                    commit_id = main["commit_id"]
                self._send(200, {"schema": "merlin-forge-checks/1",
                    "commit_id": commit_id, "required_checks": forge.required_checks("main"),
                    "check_results": forge.check_results(commit_id)})
                return
            if path == "/api/forge/events":
                try:
                    limit = int((parse_qs(parsed.query).get("limit") or ["100"])[0])
                    result = forge.events(limit)
                except (ValueError, TypeError) as exc:
                    self._send(400, {"error": "invalid_event_limit", "detail": str(exc)[:200]})
                    return
                self._send(200, {"schema": "merlin-forge-events/1", "events": result})
                return
            if path == "/api/forge/file":
                params = parse_qs(parsed.query)
                ref = (params.get("ref") or ["main"])[0]
                logical_path = (params.get("path") or [""])[0]
                content = forge.read_file(ref, logical_path)
                self._send(200, {"schema": "merlin-forge-file/1", "ref": ref,
                    "path": logical_path, "content_utf8": content.decode("utf-8"),
                    "sha256": sha256(content).hexdigest()})
                return
            if path == "/api/internal/outbox/status":
                worker_id = self._worker_actor()
                if worker_id is None:
                    self._send(401, {"error": "worker_authentication_required"})
                    return
                if learning_outbox is None:
                    self._send(503, {"error": "outbox_not_configured"})
                    return
                self._send(200, {"schema": "merlin-outbox-worker-status/1",
                                 "worker_id": worker_id, "counts": learning_outbox.counts()})
                return
            if path == "/api/research/literature":
                query_params = parse_qs(parsed.query)
                query = (query_params.get("q") or [""])[0]
                source = (query_params.get("source") or ["all"])[0]
                limit_value = (query_params.get("limit") or ["10"])[0]
                try:
                    limit = int(limit_value)
                    result = literature_search.search(query, source=source, limit=limit)
                    query_digest = sha256(query.encode("utf-8")).hexdigest()
                    store.append(
                        "/api/research/literature",
                        {"query_sha256": query_digest, "source": source, "limit": limit},
                        {"query_sha256": query_digest, "sources": result["sources_requested"],
                         "result_count": len(result["results"]),
                         "error_sources": [item["source"] for item in result["errors"]]},
                    )
                    self._send(200, result)
                except (ValueError, TypeError) as exc:
                    self._send(400, {"error": "invalid_literature_search",
                                     "detail": str(exc)[:200]})
                return
            if path == "/api/graphs/validate":
                if canonical_graph is None:
                    self._send(503, {"error": "canonical_graph_not_configured",
                                     "source": "canonical_knowledge_graph"})
                    return
                try:
                    snapshot = canonical_graph.export_snapshot()
                    graph = {
                        "nodes": [{"id": node["node_id"]} for node in snapshot["nodes"]],
                        "edges": [{"source": edge["source_id"],
                                   "target": edge["target_id"],
                                   "relation": edge["relation"]}
                                  for edge in snapshot["edges"]],
                    }
                    result = validate_graph(graph)
                    self._send(200, {
                        **result,
                        "source": "canonical_knowledge_graph",
                        "snapshot_sha256": snapshot["snapshot_sha256"],
                        "promotion_authorized": False,
                    })
                except Exception:
                    self._send(503, {"error": "canonical_graph_validation_unavailable",
                                     "source": "canonical_knowledge_graph"})
                return
            if path == "/api/learning/courses":
                actor = self._learning_actor()
                if actor is None:
                    self._send(503, {"error": "learning_identity_provider_not_configured"})
                    return
                try:
                    self._send(200, learning_platform.list_courses(actor))
                except PermissionError as exc:
                    self._send(403, {"error": "forbidden", "detail": str(exc)[:200]})
                except (ValueError, TypeError) as exc:
                    self._send(400, {"error": "invalid_request", "detail": str(exc)[:200]})
                return
            if path.startswith("/api/learning/courses/"):
                actor = self._learning_actor()
                if actor is None:
                    self._send(503, {"error": "learning_identity_provider_not_configured"})
                    return
                try:
                    parts = [unquote(part) for part in path.split("/") if part]
                    if len(parts) == 5 and parts[4] == "recommendation":
                        result = learning_platform.recommend_next_lesson(actor, parts[3], learner_store)
                        self._send(200, result)
                        return
                    if len(parts) != 4:
                        self._send(404, {"error": "not_found"})
                        return
                    query = parse_qs(parsed.query)
                    version_value = (query.get("version") or [None])[0]
                    version = int(version_value) if version_value is not None else None
                    self._send(200, learning_platform.get_course(actor, parts[3], version))
                except PermissionError as exc:
                    self._send(403, {"error": "forbidden", "detail": str(exc)[:200]})
                except KeyError:
                    # Hide whether a course exists outside the caller's tenant.
                    self._send(404, {"error": "course_not_found"})
                except (ValueError, TypeError) as exc:
                    self._send(400, {"error": "invalid_request", "detail": str(exc)[:200]})
                return
            if path in {"/api/hud/activity", "/api/hud/graph", "/api/hud/node"}:
                if hud_runtime is None:
                    self._send(503, {"error": "hud_runtime_not_configured",
                                     "mode": "labelled_demonstration_fallback"})
                    return
                environ = {
                    "PATH_INFO": path,
                    "QUERY_STRING": parsed.query,
                    "REQUEST_METHOD": "GET",
                }
                response_meta: dict[str, Any] = {}
                def start_response(status: str, headers: list[tuple[str, str]]):
                    response_meta["status"] = status
                    response_meta["headers"] = headers
                body = b"".join(hud_runtime.application(environ, start_response))
                status = int(response_meta.get("status", "503").split(" ", 1)[0])
                headers = dict(response_meta.get("headers", []))
                self._send_bytes(status, body, headers.get("Content-Type", "application/json; charset=utf-8"))
                return
            if path == "/hud":
                repo_root = Path(__file__).resolve().parents[2]
                hud_path = repo_root / "ui" / "merlin-hud" / "index.html"
                if not hud_path.is_file():
                    hud_path = repo_root / "web" / "merlin_hud.html"
                if not hud_path.is_file():
                    self._send(404, {"error": "hud_not_found"})
                    return
                self._send_bytes(200, hud_path.read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/sim/state":
                self._send(200, simulation.snapshot())
            elif path == "/api/sim/events":
                self._send(200, simulation.get_events())
            elif path == "/api/sim/replay":
                rows = store.by_kind("/api/sim/step")
                actions = [row["summary"]["last_action"] for row in rows
                           if isinstance(row.get("summary", {}).get("last_action"), str)]
                self._send(200, {"schema": "merlin-simulation-replay/1",
                                 "environment": "deterministic_simulation",
                                 "actions": actions, "replayed_actions": len(actions),
                                 "state": simulation.snapshot(),
                                 "promotion_authorized": False})
            elif path == "/api/telemetry":
                rows = store.recent(100)
                events = [row["summary"]["event"] for row in rows
                          if row["kind"] == "/api/telemetry/ingest"
                          and isinstance(row.get("summary"), dict)
                          and isinstance(row["summary"].get("event"), dict)]
                self._send(200, telemetry_view(events))
            elif path == "/api/learning/preferences":
                self._send(200, {"schema": "merlin-interaction-preferences/1",
                                 "preferences": interaction_store.preferences()})
            elif path == "/api/learning/improvements":
                latest = interaction_store.latest_analysis()
                if latest is None:
                    self._send(200, current_interaction_analysis())
                else:
                    self._send(200, {"schema": "merlin-interaction-improvement-result/1",
                                     "latest": latest,
                                     "analysis": latest["analysis"]})
            elif path == "/api/telemetry/graph":
                rows = store.by_kind("/api/telemetry/ingest", 10000)
                events = [row["summary"]["event"] for row in rows
                          if isinstance(row.get("summary"), dict)
                          and isinstance(row["summary"].get("event"), dict)]
                self._send(200, build_telemetry_graph(events))
            elif path == "/health":
                self._send(200, {"ok": True, "service": "merlin", "version": "0.4"})
            elif path == "/api/capabilities":
                self._send(200, capability_snapshot(
                    CAPABILITIES, _runtime_provider_status(),
                    outbox_configured=learning_outbox is not None))
            elif path == "/api/runtime/providers":
                self._send(200, _runtime_provider_status())
            elif path == "/api/runtime/hermes":
                if hermes_runtime is not None:
                    self._send(200, hermes_runtime.health())
                elif hermes_worker_service is None:
                    self._send(503, {"schema": "merlin-hermes-worker-service-health/1",
                                     "status": "unconfigured", "ready": False,
                                     "promotion_authority": False})
                else:
                    self._send(200, hermes_worker_service.health())
            elif path == "/api/memory":
                self._send(200, memory_vault.snapshot())
            elif path == "/api/events":
                self._send(200, {"schema": "merlin-events/1", "events": store.recent()})
            elif path in {"/api/learning/learner", "/api/learning/recommendation"}:
                query = parse_qs(parsed.query)
                learner_id = (query.get("learner_id") or [""])[0]
                if not learner_id or len(learner_id) > 200:
                    self._send(400, {"error": "learner_id_required"})
                    return
                if path == "/api/learning/recommendation":
                    curriculum_id = (query.get("curriculum_id") or [None])[0]
                    if curriculum_id not in {None, "mathematics", "b2b-ml-agentic-ai", "art-math-studio"}:
                        self._send(400, {"error": "unsupported_curriculum"})
                        return
                    result = select_next_lesson(learner_id, learner_store, learning_graph,
                                                learning_lessons, curriculum_id=curriculum_id)
                    if learning_outbox is not None:
                        minute = int(datetime.now(timezone.utc).timestamp() // 60)
                        learning_outbox.enqueue("learning-recommendation:" + learner_id + ":" + str(minute),
                            "merlin.learning.recommendation", {"learner_id": learner_id,
                            "curriculum_id": curriculum_id})
                        if learning_router is not None:
                            learning_router.run_once()
                    self._send(200, {"schema": "merlin-learning-recommendation/1", **result})
                else:
                    estimates = {}
                    for idea_id, idea in learning_graph.items():
                        estimates[idea_id] = {dimension: learner_store.estimate(
                            learner_id, idea_id, dimension).__dict__ for dimension in idea["dimensions"]}
                    self._send(200, {"schema": "merlin-learner-state/1", "learner_id": learner_id,
                                     "skills": estimates, "attempts": len(learner_store.attempts(learner_id))})
            elif path == "/api/council/roles":
                self._send(200, {"schema": "merlin-council-roles/1",
                                 "roles": [{"id": p.persona_id, "title": p.title,
                                            "temperament": p.temperament,
                                            "priorities": list(p.primary_values)}
                                           for p in PERSONAS]})
            else:
                self._send(404, {"error": "not_found"})

        def do_POST(self) -> None:
            self._request_started = perf_counter()
            path = urlparse(self.path).path
            if not self._origin_allowed():
                self._send(403, {"error": "cross_origin_request_blocked"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_BODY:
                    self._send(413 if length > MAX_BODY else 400, {"error": "invalid_body_size"})
                    return
                raw = self.rfile.read(length)
                data = json.loads(raw.decode("utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("request body must be a JSON object")

                if path == "/api/forge/branches":
                    result = forge.create_branch(data.get("name"), data.get("from_ref", "main"))
                    self._send(201, {"schema": "merlin-forge-branch-created/1", **result})
                    return
                if path == "/api/forge/jobs":
                    result = forge.enqueue_job(
                        data.get("commit_id"), data.get("job_type"), data.get("idempotency_key"),
                        max_attempts=data.get("max_attempts", 2),
                    )
                    self._send(202, {"schema": "merlin-forge-job-enqueued/1", **result})
                    return
                if path.startswith("/api/internal/forge/jobs/"):
                    worker_id = self._worker_actor()
                    if worker_id is None:
                        self._send(401, {"error": "worker_authentication_required"})
                        return
                    action = path.rsplit("/", 1)[-1]
                    if action == "claim":
                        lease = forge.claim_job(
                            worker_id, lease_seconds=data.get("lease_seconds", 120),
                            job_types=data.get("job_types"),
                        )
                        if lease is not None:
                            store.append(path, {"worker_id": worker_id, "job_id": lease["job_id"]},
                                         {"action": "claimed", "attempts": lease["attempts"]})
                        self._send(200, {"schema": "merlin-forge-job-claim/1", "lease": lease})
                        return
                    parts = path.strip("/").split("/")
                    if len(parts) != 6:
                        raise ValueError("virtual job worker path must include job ID and action")
                    job_id = unquote(parts[4])
                    lease_token = data.get("lease_token")
                    if not isinstance(lease_token, str) or not lease_token:
                        raise ValueError("lease_token is required")
                    if action == "heartbeat":
                        result = forge.heartbeat_job(
                            job_id, worker_id, lease_token,
                            lease_seconds=data.get("lease_seconds", 120),
                        )
                    elif action == "complete":
                        result = forge.complete_job(
                            job_id, worker_id, lease_token, data.get("conclusion"),
                            data.get("result", {}), data.get("log", ""),
                        )
                    else:
                        self._send(404, {"error": "unknown_virtual_job_worker_action"})
                        return
                    store.append(path, {"worker_id": worker_id, "job_id": job_id},
                                 {"action": action, "status": result.get("status", "running"),
                                  "verification_status": result.get("verification_status", "UNVERIFIED"),
                                  "promotion_authorized": False})
                    self._send(200, {"schema": "merlin-forge-job-worker-action/1", **result})
                    return
                if path == "/api/forge/checks":
                    result = forge.record_check_result(data.get("commit_id"), data.get("check_name"),
                        data.get("conclusion"), data.get("run_id"), data.get("runner_id"),
                        data.get("log", ""))
                    self._send(201, {"schema": "merlin-forge-check-result/1", **result})
                    return
                if path == "/api/forge/commits":
                    changes = data.get("changes")
                    if not isinstance(changes, dict):
                        raise ValueError("changes must be an object mapping paths to text or null")
                    result = forge.commit(data.get("branch"), data.get("message"), changes)
                    store.append(path, {"branch": result["branch"], "commit_id": result["commit_id"]},
                                 {"changed_paths": result["changed_paths"],
                                  "virtual_repository": True, "execution_performed": False})
                    self._send(201, {"schema": "merlin-forge-commit/1", **result})
                    return
                if path == "/api/forge/pulls":
                    result = forge.open_pull_request(data.get("source_branch"),
                        data.get("target_branch", "main"), data.get("title", "Untitled change"))
                    self._send(201, {"schema": "merlin-forge-pull-request/1", **result})
                    return
                if path.startswith("/api/forge/pulls/") and path.endswith("/merge"):
                    parts = path.strip("/").split("/")
                    if len(parts) != 5 or not parts[3].isdigit():
                        raise ValueError("pull request path must contain an integer ID")
                    result = forge.merge_pull_request(int(parts[3]))
                    self._send(200 if result["status"] == "merged" else 409,
                        {"schema": "merlin-forge-merge/1", **result})
                    return
                if path.startswith("/api/forge/branches/") and path.endswith("/rebase"):
                    parts = path.strip("/").split("/")
                    if len(parts) != 5:
                        raise ValueError("invalid rebase path")
                    result = forge.rebase_branch(unquote(parts[3]), data.get("onto_ref", "main"))
                    self._send(200 if result["status"] != "conflict" else 409,
                        {"schema": "merlin-forge-rebase/1", **result})
                    return
                if path.startswith("/api/forge/branches/") and path.endswith("/rollback"):
                    parts = path.strip("/").split("/")
                    if len(parts) != 5:
                        raise ValueError("invalid rollback path")
                    result = forge.rollback_branch(unquote(parts[3]), data.get("commit_id"))
                    self._send(200, {"schema": "merlin-forge-rollback/1", **result})
                    return
                if path.startswith("/api/internal/outbox/"):
                    action = path.rsplit("/", 1)[-1]
                    if action == "cancel":
                        if not self._outbox_admin_authenticated():
                            self._send(401, {"error": "outbox_admin_authentication_required"})
                            return
                        if learning_outbox is None:
                            self._send(503, {"error": "outbox_not_configured"})
                            return
                        event_id = data.get("event_id")
                        reason = data.get("reason", "")
                        if not isinstance(event_id, str) or not event_id:
                            raise ValueError("event_id is required")
                        if not isinstance(reason, str) or len(reason) > 500:
                            raise ValueError("reason must be a string of at most 500 characters")
                        result = learning_outbox.cancel(event_id, "merlin-admin", reason)
                        store.append(path, {"actor": "merlin-admin", "event_id": event_id},
                                     {"action": "cancel", "state": result["state"]})
                        self._send(200, {"schema": "merlin-outbox-admin-action/1",
                                         "event": result})
                        return
                    worker_id = self._worker_actor()
                    if worker_id is None:
                        self._send(401, {"error": "worker_authentication_required"})
                        return
                    if learning_outbox is None:
                        self._send(503, {"error": "outbox_not_configured"})
                        return
                    if action == "claim":
                        topics = data.get("topics")
                        allowed_topics = worker_topic_allowlist.get(worker_id, frozenset())
                        if not allowed_topics:
                            self._send(403, {"error": "worker_has_no_topic_grants"})
                            return
                        if (not isinstance(topics, list) or not topics or len(topics) > 20
                                or any(not isinstance(topic, str) or not topic or len(topic) > 200
                                       for topic in topics)):
                            raise ValueError("topics must be a non-empty list of at most 20 topic names")
                        if any(topic not in allowed_topics for topic in topics):
                            self._send(403, {"error": "worker_topic_not_authorized"})
                            return
                        lease = learning_outbox.claim_next(
                            worker_id, lease_seconds=data.get("lease_seconds", 60), topics=topics)
                        if lease is not None:
                            store.append(path, {"worker_id": worker_id, "event_id": lease["event_id"]},
                                         {"action": "claimed", "state": lease["state"],
                                          "attempts": lease["attempts"]})
                        self._send(200, {"schema": "merlin-outbox-claim/1", "lease": lease})
                        return
                    event_id = data.get("event_id")
                    lease_token = data.get("lease_token")
                    if not isinstance(event_id, str) or not isinstance(lease_token, str):
                        raise ValueError("event_id and lease_token are required")
                    if action == "heartbeat":
                        result = learning_outbox.heartbeat(
                            event_id, worker_id, lease_token,
                            lease_seconds=data.get("lease_seconds", 60))
                    elif action == "acknowledge":
                        payload = data.get("result")
                        if payload is not None and not isinstance(payload, dict):
                            raise ValueError("result must be an object")
                        result = learning_outbox.acknowledge(
                            event_id, worker_id, lease_token, result=payload)
                    elif action == "retry":
                        error = data.get("error")
                        if not isinstance(error, str) or not error:
                            raise ValueError("error is required")
                        result = learning_outbox.retry(
                            event_id, worker_id, lease_token, error,
                            delay_seconds=data.get("delay_seconds", 0),
                            max_attempts=data.get("max_attempts", 5))
                    else:
                        self._send(404, {"error": "not_found"})
                        return
                    store.append(path, {"worker_id": worker_id, "event_id": event_id},
                                 {"action": action, "state": result["state"],
                                  "attempts": result["attempts"]})
                    self._send(200, {"schema": "merlin-outbox-worker-action/1",
                                     "event": result})
                    return

                if path == "/api/graphs/validate":
                    graph = data.get("graph", data)
                    result = validate_graph(graph)
                    store.append(path, {"graph_sha256": result["graph_sha256"]},
                                 {"valid": result["valid"], "node_count": result["node_count"],
                                  "edge_count": result["edge_count"], "errors": result["errors"]})
                    self._send(200, {**result, "source": "request_preview",
                                     "promotion_authorized": False})
                    return
                if path == "/api/learning/courses":
                    actor = self._learning_actor()
                    if actor is None:
                        self._send(503, {"error": "learning_identity_provider_not_configured"})
                        return
                    result = learning_platform.create_course(
                        actor, data.get("slug"), data.get("title"), data.get("description", ""))
                    store.append(path, {"course_id": result["course_id"]},
                                 {"action": "course.created", "version": result["version"],
                                  "manifest_sha256": result["manifest_sha256"]})
                    self._send(201, result)
                    return
                if path.startswith("/api/learning/courses/"):
                    actor = self._learning_actor()
                    if actor is None:
                        self._send(503, {"error": "learning_identity_provider_not_configured"})
                        return
                    parts = [unquote(part) for part in path.split("/") if part]
                    if len(parts) != 5:
                        self._send(404, {"error": "not_found"})
                        return
                    course_id, action = parts[3], parts[4]
                    if action == "manifest":
                        result = learning_platform.update_manifest(actor, course_id, data.get("manifest"))
                    elif action == "review":
                        result = learning_platform.review_course(
                            actor, course_id, data.get("version"), data.get("decision"), data.get("notes", ""))
                    elif action == "publish":
                        result = learning_platform.publish_course(actor, course_id)
                    elif action == "revisions":
                        result = learning_platform.create_revision(actor, course_id)
                    elif action == "enroll":
                        result = learning_platform.enroll(actor, course_id, data.get("learner_id"))
                    else:
                        self._send(404, {"error": "not_found"})
                        return
                    store.append(path, {"course_id": course_id, "action": action},
                                 {"result_sha256": sha256(_json_bytes(result)).hexdigest()})
                    self._send(200, result)
                    return
                if path == "/api/learning/improvements/evaluate":
                    analysis = current_interaction_analysis()
                    receipt = interaction_store.save_analysis(analysis)
                    store.append(path, {"analysis_sha256": receipt["analysis_sha256"]},
                                 {"analysis_id": receipt["analysis_id"],
                                  "analysis_sha256": receipt["analysis_sha256"],
                                  "telemetry_samples": receipt["telemetry_samples"],
                                  "feedback_samples": receipt["feedback_samples"],
                                  "proposal_count": len(analysis["proposals"]),
                                  "promotion_authorized": False})
                    self._send(201, {"schema": "merlin-interaction-improvement-result/1",
                                     "receipt": receipt, "analysis": analysis,
                                     "promotion_authorized": False})
                    return
                if path == "/api/learning/preferences":
                    preferences = interaction_store.set_preferences(data)
                    store.append(path, {"changed_preferences": sorted(data)},
                                 {"preferences": preferences, "raw_content_stored": False})
                    self._send(200, {"schema": "merlin-interaction-preferences/1",
                                     "preferences": preferences})
                    return
                if path in {"/api/memory/preferences", "/api/memory/projects"}:
                    if data.get("approved") is not True:
                        self._send(403, {"error": "explicit_approval_required",
                                         "detail": "Saving long-term memory requires an explicit user action."})
                        return
                    if path == "/api/memory/preferences":
                        receipt = memory_vault.set_preference(data.get("key"), data.get("value"))
                        store.append(path, {"key": receipt["key"],
                                            "value_sha256": receipt["value_sha256"]},
                                     {"saved": True, "version": receipt["version"],
                                      "raw_memory_value_in_event_ledger": False})
                        self._send(201, {"schema": "merlin-memory-save/1",
                                         "kind": "preference", "key": receipt["key"],
                                         "version": receipt["version"]})
                    else:
                        receipt = memory_vault.set_project(data.get("name"), data.get("status"))
                        store.append(path, {"name": receipt["name"],
                                            "status_sha256": receipt["status_sha256"]},
                                     {"saved": True, "version": receipt["version"],
                                      "raw_memory_value_in_event_ledger": False})
                        self._send(201, {"schema": "merlin-memory-save/1",
                                         "kind": "project", "name": receipt["name"],
                                         "version": receipt["version"]})
                    return
                if path == "/api/interaction/feedback":
                    result = interaction_store.record_feedback(data)
                    # Store only the event ID and categorical outcome summary; never free text.
                    store.append(path, {"event_id": result["event_id"]},
                                 {"accepted": True, "duplicate": result["duplicate"],
                                  "domain": data.get("domain", "general"),
                                  "task_type": data.get("task_type"),
                                  "outcome": data.get("outcome"),
                                  "friction_code": data.get("friction_code"),
                                  "correction_type": data.get("correction_type"),
                                  "satisfaction": data.get("satisfaction")})
                    self._send(202, {"schema": "merlin-interaction-feedback/1", **result,
                                     "raw_conversation_content_stored": False})
                    return
                if path == "/api/research/transfers/preview":
                    discovery = data.get("discovery", data)
                    requested_targets = data.get("requested_targets")
                    if not isinstance(discovery, dict):
                        raise ValueError("discovery must be an object")
                    if requested_targets is not None and (
                        not isinstance(requested_targets, list)
                        or any(not isinstance(item, str) for item in requested_targets)
                    ):
                        raise ValueError("requested_targets must be a list of subsystem identifiers")
                    preview = preview_transfers(discovery, requested_targets)
                    storage_status = "preview_only"
                    artifact_ref = None
                    project_id = data.get("project_id")
                    if project_id is not None:
                        if not isinstance(project_id, str) or not project_id.strip():
                            raise ValueError("project_id must be a nonblank string")
                        if canonical_registry is None:
                            self._send(503, {"error": "canonical_registry_unavailable",
                                             "storage_status": "not_persisted"})
                            return
                        canonical_registry.inventory(project_id)
                        artifact_bytes = _json_bytes(preview)
                        logical_path = "math-transfers/" + preview["preview_sha256"] + ".json"
                        digest = canonical_registry.put_artifact(
                            project_id, logical_path, artifact_bytes,
                            "application/vnd.merlin.math-transfer-preview+json")
                        verified = canonical_registry.verify_artifact(digest)
                        if not verified:
                            self._send(503, {"error": "canonical_registry_verification_failed",
                                             "storage_status": "not_verified"})
                            return
                        artifact_ref = {"project_id": project_id, "logical_path": logical_path,
                                        "sha256": digest, "verified": True}
                        storage_status = "canonical_registry"
                    store.append(path, {"preview_sha256": preview["preview_sha256"],
                                        "discovery_id": preview["discovery"]["discovery_id"],
                                        "project_id": project_id},
                                 {"candidate_count": preview["candidate_count"],
                                  "storage_status": storage_status,
                                  "promotion_authorized": False})
                    self._send(200, {"schema": preview["schema"], "preview": preview,
                                     "storage_status": storage_status, "artifact_ref": artifact_ref,
                                     "promotion_authorized": False})
                    return

                if path == "/api/intents/compile":
                    intent_data = data.get("intent", data)
                    assets_data = data.get("assets", [])
                    continuity_data = data.get("continuity")
                    if not isinstance(intent_data, dict) or not isinstance(assets_data, list):
                        raise ValueError("intent must be an object and assets must be a list")

                    def string_field(value: Any, field_name: str) -> str:
                        if not isinstance(value, str):
                            raise ValueError(field_name + " must be a string")
                        return value

                    def string_list(value: Any, field_name: str) -> tuple[str, ...]:
                        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                            raise ValueError(field_name + " must be a list of strings")
                        return tuple(value)

                    duration = intent_data.get("duration_seconds")
                    if duration is not None and (isinstance(duration, bool) or not isinstance(duration, int)):
                        raise ValueError("duration_seconds must be an integer")
                    intent = IntentSpec(
                        goal=string_field(intent_data.get("goal", ""), "goal"),
                        domain=string_field(intent_data.get("domain", ""), "domain"),
                        deliverable=string_field(intent_data.get("deliverable", ""), "deliverable"),
                        constraints=string_list(intent_data.get("constraints", []), "constraints"),
                        exclusions=string_list(intent_data.get("exclusions", []), "exclusions"),
                        success_criteria=string_list(intent_data.get("success_criteria", []), "success_criteria"),
                        audience=string_field(intent_data.get("audience", ""), "audience"),
                        target_backend=string_field(intent_data.get("target_backend", "generic"), "target_backend"),
                        duration_seconds=duration,
                    )
                    assets = []
                    for row in assets_data:
                        if not isinstance(row, dict):
                            raise ValueError("each asset must be an object")
                        metadata = row.get("metadata", {})
                        if not isinstance(metadata, dict):
                            raise ValueError("asset metadata must be an object")
                        assets.append(Asset(
                            asset_id=string_field(row.get("asset_id", ""), "asset_id"),
                            name=string_field(row.get("name", ""), "asset name"),
                            kind=string_field(row.get("kind", ""), "asset kind"),
                            sha256=string_field(row.get("sha256", ""), "asset sha256"),
                            role=string_field(row.get("role", "reference"), "asset role"),
                            # Trust level is server-assigned below; never accept a caller's
                            # assertion that an uploaded/reference asset is authoritative.
                            authority="user_supplied",
                            locator=string_field(row.get("locator", ""), "asset locator"),
                            metadata=metadata,
                        ))
                    continuity = None
                    if continuity_data is not None:
                        if not isinstance(continuity_data, dict):
                            raise ValueError("continuity must be an object")
                        continuity = ContinuityState(
                            checkpoint_id=string_field(continuity_data.get("checkpoint_id", ""), "checkpoint_id"),
                            prior_state=string_field(continuity_data.get("prior_state", ""), "prior_state"),
                            stable_entity_ids=string_list(
                                continuity_data.get("stable_entity_ids", []), "stable_entity_ids"),
                            next_step=string_field(continuity_data.get("next_step", ""), "next_step"),
                        )
                    bundle = compile_directive(intent, assets, continuity)
                    storage_status = "preview_only"
                    artifact_ref = None
                    project_id = data.get("project_id")
                    if project_id is not None:
                        project_id = string_field(project_id, "project_id")
                        if not project_id.strip():
                            raise ValueError("project_id cannot be blank")
                        if canonical_registry is None:
                            self._send(503, {"error": "canonical_registry_unavailable",
                                             "storage_status": "not_persisted"})
                            return
                        # inventory() verifies that the target project already exists;
                        # the compiler must not silently create a new project namespace.
                        project_inventory = canonical_registry.inventory(project_id)
                        project_digests = {item["digest"] for item in project_inventory["artifacts"]}
                        verified_assets = []
                        for asset in assets:
                            if asset.sha256 not in project_digests or not canonical_registry.verify_artifact(asset.sha256):
                                raise ValueError("asset sha256 must reference a verified artifact in the target project registry")
                            verified_assets.append(Asset(
                                asset_id=asset.asset_id, name=asset.name, kind=asset.kind,
                                sha256=asset.sha256, role=asset.role,
                                authority="canonical_registry_verified",
                                locator=asset.locator, metadata=asset.metadata,
                            ))
                        assets = verified_assets
                        # Recompile so the persisted directive records server-verified
                        # provenance, not caller-supplied trust labels.
                        bundle = compile_directive(intent, assets, continuity)
                        artifact_bytes = _json_bytes(bundle)
                        logical_path = "intents/" + bundle["directive_sha256"] + ".json"
                        artifact_digest = canonical_registry.put_artifact(
                            project_id, logical_path, artifact_bytes,
                            "application/vnd.merlin.directive-bundle+json")
                        artifact_ref = {
                            "project_id": project_id, "logical_path": logical_path,
                            "sha256": artifact_digest, "verified": canonical_registry.verify_artifact(artifact_digest),
                        }
                        if not artifact_ref["verified"]:
                            self._send(503, {"error": "canonical_registry_verification_failed",
                                             "storage_status": "not_verified"})
                            return
                        storage_status = "canonical_registry"
                    store.append(path, {"directive_sha256": bundle["directive_sha256"],
                                        "domain": bundle["domain"], "project_id": project_id},
                                 {"directive_sha256": bundle["directive_sha256"],
                                  "asset_count": len(assets), "storage_status": storage_status,
                                  "artifact_sha256": artifact_ref["sha256"] if artifact_ref else None,
                                  "execution_authorized": False})
                    self._send(200, {
                        "schema": "merlin-directive-bundle/1", "bundle": bundle,
                        "storage_status": storage_status, "artifact_ref": artifact_ref,
                        "execution_authorized": False, "promotion_authorized": False,
                    })
                    return

                if path == "/api/learning/attempt":
                    scored_event = score_attempt_event(data)
                    result = learner_store.record_attempt(scored_event)
                    if learning_outbox is not None:
                        learning_outbox.enqueue("learning-attempt:" + str(scored_event.get("attempt_id", "")),
                            "merlin.learning.attempt", scored_event)
                        if learning_router is not None:
                            learning_router.run_once()
                    store.append(path, {"attempt_id": scored_event.get("attempt_id"),
                                        "learner_id": scored_event.get("learner_id")},
                                 {"state": result.get("state"), "idea_id": scored_event.get("idea_id"),
                                  "dimension": scored_event.get("dimension"),
                                  "scoring_source": scored_event.get("scoring_source")})
                    self._send(202, {"schema": "merlin-learning-attempt/1", "accepted": True, **result})
                    return
                if path == "/api/telemetry/ingest":
                    if not interaction_store.preferences()["aggregate_telemetry"]:
                        self._send(202, {"accepted": False, "reason": "telemetry_disabled",
                                         "promotion_authorized": False})
                        return
                    event = normalize_event(data)
                    store.append(path, {"event_id": event["event_id"], "source": event["source"]},
                                 {"event": event})
                    self._send(202, {"accepted": True, "event": event,
                                     "promotion_authorized": False})
                    return
                if path == "/api/sim/step":
                    action = data.get("action", "")
                    if not isinstance(action, str):
                        raise ValueError("simulation action must be a string")
                    result = simulation.step(action)
                    store.append(path, {"action": action, "tick": result["state"]["tick"]},
                                 {"simulation_only": True, "last_action": action,
                                  "tick": result["state"]["tick"],
                                  "progress": result["state"]["progress"],
                                  "uncertainty": result["state"]["uncertainty"]})
                    sim_event = normalize_event({
                        "source": "simulation", "kind": "operator.action",
                        "run_id": "simulation-session", "task_id": "simulation-control",
                        "payload": {"action": action, "tick": result["state"]["tick"],
                                    "simulation_only": True},
                    })
                    store.append("/api/telemetry/ingest",
                                 {"event_id": sim_event["event_id"], "source": "simulation"},
                                 {"event": sim_event})
                    self._send(200, result)
                    return
                if path == "/api/council/prepare":
                    question = data.get("question", "")
                    context = data.get("context", "")
                    verbosity = data.get("verbosity", "lively")
                    if not isinstance(question, str) or not isinstance(context, str):
                        raise ValueError("question and context must be strings")
                    result = {
                        "schema": "merlin-council-packets/1",
                        "packets": build_deliberation_packets(question, context, verbosity),
                        "promotion_authorized": False,
                    }
                    store.append(path, {"question": question, "verbosity": verbosity},
                                 {"persona_count": len(PERSONAS), "verbosity": verbosity})
                    self._send(200, result)
                    return
                if path == "/api/council/run":
                    question = data.get("question", "")
                    context = data.get("context", "")
                    verbosity = data.get("verbosity", "lively")
                    rounds = data.get("rounds", 1)
                    if not isinstance(question, str) or not isinstance(context, str):
                        raise ValueError("question and context must be strings")
                    council_started = perf_counter()
                    result = run_local_council(question, context, verbosity, rounds)
                    council_duration_ms = (perf_counter() - council_started) * 1000.0
                    transcript_digest = sha256(_json_bytes(result)).hexdigest()
                    result["transcript_sha256"] = transcript_digest
                    store.append(path, {"question": question, "verbosity": verbosity, "rounds": rounds},
                                 {"model": result["model"], "opening_count": len(result["opening_positions"]),
                                  "cross_examination_count": len(result["cross_examination"]),
                                  "transcript_sha256": transcript_digest})
                    council_event = normalize_event({
                        "source": "model_output", "kind": "model.inference",
                        "run_id": transcript_digest, "task_id": "council-deliberation",
                        "model_id": str(result.get("model", "local-unidentified")),
                        "duration_ms": council_duration_ms,
                        "payload": {"opening_count": len(result["opening_positions"]),
                                    "cross_examination_count": len(result["cross_examination"]),
                                    "transcript_sha256": transcript_digest},
                        "evidence_refs": ["sha256:" + transcript_digest],
                    })
                    store.append("/api/telemetry/ingest",
                                 {"event_id": council_event["event_id"], "source": "model_output"},
                                 {"event": council_event})
                    self._send(200, result)
                    return
                if path == "/api/speech":
                    if os.environ.get("MERLIN_TTS_QUALIFIED") != "1":
                        self._send(503, {"error": "tts_not_qualified"})
                        return
                    endpoint = _loopback_endpoint("MERLIN_TTS_URL", "http://127.0.0.1:8880/v1/audio/speech")
                    request = Request(endpoint, data=raw, headers={"Content-Type": "application/json"}, method="POST")
                    with urlopen(request, timeout=60) as response:
                        audio = response.read(MAX_PROXY_RESPONSE + 1)
                        if len(audio) > MAX_PROXY_RESPONSE:
                            self._send(502, {"error": "tts_response_too_large"})
                            return
                        content_type = response.headers.get("Content-Type", "audio/wav")
                    store.append(path, data, {"bytes": len(audio), "content_type": content_type})
                    _append_component_event(store, source="model_output", kind="model.inference",
                        component="tts_adapter", task_id="speech",
                        payload={"response_bytes": len(audio), "content_type": content_type},
                        duration_ms=(perf_counter() - self._request_started) * 1000.0,
                        model_id=os.environ.get("MERLIN_TTS_MODEL"))
                    self._send_bytes(200, audio, content_type)
                    return
                if path == "/api/chat":
                    provider = data.get("provider", "auto")
                    if provider not in {"auto", "local", "cloud"}:
                        raise ValueError("provider must be auto, local, or cloud")
                    remote_url = os.environ.get("MERLIN_REMOTE_MODEL_URL", "").strip()
                    remote_configured = bool(remote_url)
                    use_cloud = provider == "cloud" or (provider == "auto" and remote_configured)
                    if use_cloud:
                        if os.environ.get("MERLIN_REMOTE_MODEL_QUALIFIED") != "1":
                            self._send(503, {"error": "remote_model_not_qualified"})
                            return
                        endpoint, api_key = _remote_model_endpoint()
                        selected_model = os.environ.get("MERLIN_REMOTE_MODEL_NAME", os.environ.get("MERLIN_MODEL_NAME", "")).strip()
                    else:
                        if os.environ.get("MERLIN_MODEL_QUALIFIED") != "1":
                            self._send(503, {"error": "model_not_qualified", "detail": "The local model is not qualified or configured."})
                            return
                        endpoint = _loopback_endpoint("MERLIN_MODEL_URL", "http://127.0.0.1:8080/v1/chat/completions")
                        api_key = ""
                        selected_model = os.environ.get("MERLIN_LOCAL_MODEL", os.environ.get("MERLIN_MODEL_NAME", "")).strip()
                    upstream_payload = dict(data)
                    upstream_payload.pop("provider", None)
                    if not upstream_payload.get("model"):
                        upstream_payload["model"] = selected_model
                    if not upstream_payload.get("model"):
                        self._send(503, {"error": "model_name_not_configured"})
                        return
                    upstream_raw = _json_bytes(upstream_payload)
                    headers = {"Content-Type": "application/json", "Accept": "text/event-stream, application/json"}
                    if api_key:
                        headers["Authorization"] = "Bearer " + api_key
                    request = Request(endpoint, data=upstream_raw, headers=headers, method="POST")
                    with urlopen(request, timeout=180) as response:
                        content_type = response.headers.get("Content-Type", "application/json")
                        wants_stream = bool(data.get("stream")) and "text/event-stream" in content_type.lower()
                        if wants_stream:
                            self.send_response(200)
                            self.send_header("Content-Type", content_type)
                            self.send_header("Cache-Control", "no-cache, no-transform")
                            self.send_header("X-Accel-Buffering", "no")
                            self.send_header("Connection", "close")
                            self.end_headers()
                            total = 0
                            while True:
                                chunk = response.read(8192)
                                if not chunk:
                                    break
                                total += len(chunk)
                                if total > 64000000:
                                    raise ValueError("stream exceeded 64 MB safety limit")
                                self.wfile.write(chunk)
                                self.wfile.flush()
                            self._record_boundary(200, total)
                            store.append(path, data, {"streamed": True, "bytes": total, "provider_host": urlsplit(endpoint).hostname})
                            _append_component_event(store, source="model_output", kind="model.inference",
                                component="chat_adapter", task_id="chat",
                                payload={"streamed": True, "response_bytes": total,
                                         "provider_host": urlsplit(endpoint).hostname},
                                duration_ms=(perf_counter() - self._request_started) * 1000.0,
                                model_id=os.environ.get("MERLIN_MODEL_NAME"))
                            return
                        body = response.read(MAX_PROXY_RESPONSE + 1)
                        if len(body) > MAX_PROXY_RESPONSE:
                            self._send(502, {"error": "model_response_too_large"})
                            return
                    if "application/json" in content_type.lower():
                        try:
                            model_result = json.loads(body.decode("utf-8"))
                            summary = {"model": model_result.get("model"), "choices": len(model_result.get("choices", [])), "provider_host": urlsplit(endpoint).hostname}
                        except (ValueError, AttributeError):
                            summary = {"bytes": len(body), "provider_host": urlsplit(endpoint).hostname}
                    else:
                        summary = {"bytes": len(body), "content_type": content_type, "provider_host": urlsplit(endpoint).hostname}
                    store.append(path, data, summary)
                    _append_component_event(store, source="model_output", kind="model.inference",
                        component="chat_adapter", task_id="chat",
                        payload={"streamed": False, "response_bytes": len(body),
                                 "provider_host": urlsplit(endpoint).hostname,
                                 "model": summary.get("model")},
                        duration_ms=(perf_counter() - self._request_started) * 1000.0,
                        model_id=summary.get("model") or os.environ.get("MERLIN_MODEL_NAME"))
                    self._send_bytes(200, body, content_type)
                    return
                if path == "/api/ideonomy/rank":
                    ideas = [_idea(row) for row in data.get("ideas", [])]
                    result = rank_ideas(ideas, int(data.get("limit", 8)))
                    summary = {"accepted": len(result["accepted"]), "rejected": len(result["rejected"])}
                elif path == "/api/analogy/validate":
                    result = validate_analogy(_analogy(data))
                    summary = {"accepted": result["accepted"], "reasons": len(result["reasons"])}
                elif path == "/api/rsi/qualify":
                    result = qualify_rsi_candidate(PromotionPacket(**data))
                    summary = {"status": result["status"], "failed_gates": result["failed_gates"]}
                    verifier_event = normalize_event({
                        "source": "verifier", "kind": "verification.completed",
                        "run_id": sha256(_json_bytes(data)).hexdigest(),
                        "task_id": "rsi-qualification",
                        "payload": {"status": result["status"],
                                    "failed_gates": result["failed_gates"],
                                    "promotion_authorized": False},
                    })
                    store.append("/api/telemetry/ingest",
                                 {"event_id": verifier_event["event_id"], "source": "verifier"},
                                 {"event": verifier_event})
                elif path == "/api/geometry/validate":
                    _spec, result = _geometry(data)
                    summary = {"valid": result["valid"], "issues": len(result["issues"])}
                elif path == "/api/netlist/validate":
                    issues = [issue.__dict__ for issue in validate_netlist(_netlist(data))]
                    result = {"valid": not issues, "issues": issues}
                    summary = {"valid": result["valid"], "issues": len(issues)}
                else:
                    self._send(404, {"error": "not_found"})
                    return

                store.append(path, data, summary)
                self._send(200, result)
            except PermissionError as exc:
                self._send(403, {"error": "learning_disabled", "detail": str(exc)[:200]})
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                self._send(400, {"error": "invalid_request", "detail": str(exc)[:300]})
            except LeaseConflict as exc:
                self._send(409, {"error": "outbox_lease_conflict", "detail": str(exc)[:200]})
            except RuntimeError as exc:
                self._send(503, {"error": "council_model_unavailable", "detail": str(exc)[:200]})
            except (URLError, HTTPError, TimeoutError, OSError) as exc:
                self._send(503, {"error": "local_adapter_unavailable", "detail": str(exc)[:200]})
            except Exception:
                self._send(500, {"error": "internal_error"})

        def do_DELETE(self) -> None:
            self._request_started = perf_counter()
            parsed = urlparse(self.path)
            if not self._origin_allowed():
                self._send(403, {"error": "cross_origin_request_blocked"})
                return
            try:
                query = parse_qs(parsed.query)
                if parsed.path == "/api/memory/preferences":
                    key = (query.get("key") or [""])[0]
                    deleted = memory_vault.delete_preference(key)
                    store.append("/api/memory/preferences/delete", {"key": key},
                                 {"deleted": deleted, "raw_memory_value_in_event_ledger": False})
                    self._send(200, {"schema": "merlin-memory-delete/1",
                                     "kind": "preference", "deleted": deleted})
                    return
                if parsed.path == "/api/memory/projects":
                    name = (query.get("name") or [""])[0]
                    deleted = memory_vault.delete_project(name)
                    store.append("/api/memory/projects/delete", {"name": name},
                                 {"deleted": deleted, "raw_memory_value_in_event_ledger": False})
                    self._send(200, {"schema": "merlin-memory-delete/1",
                                     "kind": "project", "deleted": deleted})
                    return
                if parsed.path != "/api/interaction/feedback":
                    self._send(404, {"error": "not_found"})
                    return
                session_id = (query.get("session_id") or [""])[0]
                deleted = interaction_store.delete_session_feedback(session_id)
                store.append("/api/interaction/feedback/delete", {"session_id": session_id},
                             {"deleted_feedback_events": deleted})
                self._send(200, {"schema": "merlin-interaction-feedback-deletion/1",
                                 "deleted_feedback_events": deleted,
                                 "scope": "categorical feedback for this opaque session only",
                                 "raw_conversation_content_stored": False})
            except ValueError as exc:
                self._send(400, {"error": "invalid_request", "detail": str(exc)[:200]})

        def log_message(self, fmt: str, *args: Any) -> None:
            # Do not log request bodies, prompts, or voice content.
            return

    return Handler


def _build_optional_hud_runtime(
    canonical_registry: Any | None = None,
    canonical_graph: Any | None = None,
    outbox: Any | None = None,
    hypotheses: Any | None = None,
):
    """Bind explicit canonical stores; never substitute demo stores for configured ones."""
    from .hud_runtime import build_hud_runtime
    if canonical_registry is not None and canonical_graph is not None and outbox is not None:
        return build_hud_runtime(
            registry=canonical_registry, graph=canonical_graph,
            outbox=outbox, hypotheses=hypotheses,
        )
    registry_root = os.environ.get("MERLIN_REGISTRY_ROOT", "").strip()
    graph_path = os.environ.get("MERLIN_GRAPH_DB_PATH", "").strip()
    outbox_path = os.environ.get("MERLIN_OUTBOX_DB_PATH", "").strip()
    if not registry_root or not graph_path or not outbox_path:
        return None
    registry_db = Path(registry_root) / "merlin.sqlite3"
    if not registry_db.is_file() or not Path(graph_path).is_file() or not Path(outbox_path).is_file():
        return None
    from .project_registry import MerlinRegistry
    from .knowledge_graph import MerlinKnowledgeGraph
    from .event_outbox import MerlinEventOutbox
    from .hypothesis_ledger import HypothesisLedger
    hypotheses_path = os.environ.get("MERLIN_HYPOTHESES_DB_PATH", "").strip()
    try:
        hypotheses = HypothesisLedger(hypotheses_path) if hypotheses_path and Path(hypotheses_path).is_file() else None
        return build_hud_runtime(
            registry=canonical_registry or MerlinRegistry(registry_root),
            graph=MerlinKnowledgeGraph(graph_path),
            outbox=MerlinEventOutbox(outbox_path),
            hypotheses=hypotheses,
        )
    except Exception as exc:
        print("Merlin HUD integration unavailable: " + type(exc).__name__)
        return None

def serve(port: int = 8765, db_path: str | None = None,
          learning_identity_resolver: Any | None = None,
          hermes_worker_service: Any | None = None,
          hermes_runtime: Any | None = None) -> None:
    if hermes_runtime is not None and hermes_worker_service is not None:
        raise ValueError("pass hermes_runtime or hermes_worker_service, not both")
    if hermes_runtime is not None:
        hermes_worker_service = hermes_runtime.service
    if learning_identity_resolver is None:
        learning_identity_resolver = learning_identity_resolver_from_environment()
    runtime_default_db = (
        str(hermes_runtime.root / "events.sqlite3") if hermes_runtime is not None else
        str(Path.home() / ".local" / "share" / "merlin" / "events.sqlite3")
    )
    target = db_path or os.environ.get("MERLIN_DB_PATH", runtime_default_db)
    store = EventStore(target)
    learner_db = os.environ.get("MERLIN_LEARNER_DB_PATH", target)
    learner_store = LearnerStore(learner_db)
    outbox_path = os.environ.get("MERLIN_OUTBOX_DB_PATH", "").strip()
    learning_outbox = (
        hermes_runtime.outbox if hermes_runtime is not None else
        MerlinEventOutbox(outbox_path) if outbox_path else None
    )
    canonical_registry = hermes_runtime.registry if hermes_runtime is not None else None
    registry_root = os.environ.get("MERLIN_REGISTRY_ROOT", "").strip()
    registry_db = Path(registry_root) / "merlin.sqlite3" if registry_root else None
    if hermes_runtime is None and registry_db is not None and registry_db.is_file():
        from .project_registry import MerlinRegistry
        canonical_registry = MerlinRegistry(registry_root)
    canonical_graph = hermes_runtime.graph if hermes_runtime is not None else None
    if canonical_graph is None:
        graph_path = os.environ.get("MERLIN_GRAPH_DB_PATH", "").strip()
        if graph_path and Path(graph_path).is_file():
            from .knowledge_graph import MerlinKnowledgeGraph
            canonical_graph = MerlinKnowledgeGraph(graph_path)
    hud_runtime = _build_optional_hud_runtime(
        canonical_registry=canonical_registry,
        canonical_graph=canonical_graph,
        outbox=learning_outbox,
        hypotheses=hermes_runtime.ledger if hermes_runtime is not None else None,
    )
    server = ThreadingHTTPServer(("127.0.0.1", port),
        make_handler(store, hud_runtime, learner_store, learning_outbox,
                     canonical_registry, learning_identity_resolver=learning_identity_resolver,
                     canonical_graph=canonical_graph,
                     hermes_worker_service=hermes_worker_service,
                     hermes_runtime=hermes_runtime))
    hud_runtime_started = False
    hermes_service_started = False
    shutdown_requested = Event()
    previous_signal_handlers = {}

    def _request_shutdown(signum, frame):
        if not shutdown_requested.is_set():
            shutdown_requested.set()
            Thread(
                target=server.shutdown,
                name="merlin-api-signal-shutdown",
                daemon=True,
            ).start()

    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            previous_signal_handlers[signum] = signal.signal(signum, _request_shutdown)
        except ValueError:
            # serve() may be embedded from a non-main thread; the process manager
            # can still stop it through the returned/injected service lifecycle.
            break
    try:
        if hud_runtime is not None:
            hud_runtime.start()
            hud_runtime_started = True
        if hermes_runtime is not None:
            hermes_service_started = bool(hermes_runtime.start())
        elif hermes_worker_service is not None:
            hermes_service_started = bool(hermes_worker_service.start())
        print(f"Merlin MVP API listening on http://127.0.0.1:{port}")
        print("Merlin HUD: canonical graph/event stores connected" if hud_runtime
              else "Merlin HUD: labelled demonstration fallback (canonical store paths not configured)")
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        for signum, previous_handler in previous_signal_handlers.items():
            signal.signal(signum, previous_handler)
        if hud_runtime_started:
            hud_runtime.stop()
        if hermes_service_started:
            if hermes_runtime is not None:
                hermes_runtime.stop(timeout_seconds=10)
            else:
                hermes_worker_service.stop(timeout_seconds=10)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run the loopback-only Merlin MVP API")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", default=None)
    args = parser.parse_args()
    serve(args.port, args.db)
