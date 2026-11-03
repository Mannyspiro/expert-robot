"""Loopback-only Merlin MVP API.

Provides deterministic research/engineering contracts and an append-only
metadata event ledger. Model, image and video generation are reported as
unconfigured until a real adapter is connected.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sqlite3
from typing import Any
from urllib.parse import urlparse, urlsplit
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from .council import PERSONAS, build_deliberation_packets
from .research import (
    AnalogyMap, Idea, PromotionPacket, qualify_rsi_candidate, rank_ideas,
    validate_analogy,
)
from .engineering.geometry import GeometrySpec, Point3D, validate_geometry, bounding_box
from .engineering.netlist import Component, Connection, Net, Netlist, validate_netlist

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


def _remote_model_endpoint() -> tuple[str, str]:
    """Return an explicitly allowlisted HTTPS OpenAI-compatible endpoint."""
    endpoint = os.environ.get("MERLIN_REMOTE_MODEL_URL", "").strip()
    api_key = os.environ.get("MERLIN_REMOTE_API_KEY", "").strip()
    allowed = {host.strip().lower() for host in os.environ.get("MERLIN_REMOTE_ALLOWED_HOSTS", "").split(",") if host.strip()}
    if not endpoint or not api_key or not allowed:
        raise ValueError("remote model requires URL, API key, and explicit allowed-host list")
    parsed = urlsplit(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.lower() not in allowed or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("remote model URL must use HTTPS and an explicitly allowlisted host")
    return endpoint, api_key


class EventStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                request_sha256 TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""")

    def append(self, kind: str, request: dict[str, Any], summary: dict[str, Any]) -> None:
        digest = sha256(_json_bytes(request)).hexdigest()
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT INTO events(kind,request_sha256,summary_json,created_at) VALUES(?,?,?,?)",
                (kind, digest, json.dumps(summary, sort_keys=True), datetime.now(timezone.utc).isoformat()),
            )

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as db:
            rows = db.execute(
                "SELECT id,kind,request_sha256,summary_json,created_at FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"id": row[0], "kind": row[1], "request_sha256": row[2],
             "summary": json.loads(row[3]), "created_at": row[4]}
            for row in rows
        ]


CAPABILITIES = [
    {"id": "council.roles", "status": "AVAILABLE", "evidence": "deterministic simulated persona registry"},
    {"id": "council.deliberation.prepare", "status": "AVAILABLE", "evidence": "role-specific prompt packets and auditable self-map contract"},
    {"id": "research.ideonomy.rank", "status": "AVAILABLE", "evidence": "unit-tested deterministic candidate ranking"},
    {"id": "research.analogy.validate", "status": "AVAILABLE", "evidence": "unit-tested invariant and boundary checks"},
    {"id": "research.rsi.qualify", "status": "AVAILABLE", "evidence": "fail-closed qualification contract"},
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


def make_handler(store: EventStore):
    class Handler(BaseHTTPRequestHandler):
        server_version = "MerlinMVP/0.3"

        def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            body = _json_bytes(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/health":
                self._send(200, {"ok": True, "service": "merlin", "version": "0.3"})
            elif path == "/api/capabilities":
                self._send(200, {"schema": "merlin-capabilities/1", "capabilities": CAPABILITIES})
            elif path == "/api/events":
                self._send(200, {"schema": "merlin-events/1", "events": store.recent()})
            elif path == "/api/council/roles":
                self._send(200, {"schema": "merlin-council-roles/1",
                                 "roles": [{"id": p.persona_id, "title": p.title,
                                            "temperament": p.temperament,
                                            "priorities": list(p.primary_values)}
                                           for p in PERSONAS]})
            else:
                self._send(404, {"error": "not_found"})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_BODY:
                    self._send(413 if length > MAX_BODY else 400, {"error": "invalid_body_size"})
                    return
                raw = self.rfile.read(length)
                data = json.loads(raw.decode("utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("request body must be a JSON object")

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
                if path == "/api/speech":
                    endpoint = _loopback_endpoint("MERLIN_TTS_URL", "http://127.0.0.1:8880/v1/audio/speech")
                    request = Request(endpoint, data=raw, headers={"Content-Type": "application/json"}, method="POST")
                    with urlopen(request, timeout=60) as response:
                        audio = response.read(MAX_PROXY_RESPONSE + 1)
                        if len(audio) > MAX_PROXY_RESPONSE:
                            self._send(502, {"error": "tts_response_too_large"})
                            return
                        content_type = response.headers.get("Content-Type", "audio/wav")
                    store.append(path, data, {"bytes": len(audio), "content_type": content_type})
                    self._send_bytes(200, audio, content_type)
                    return
                if path == "/api/chat":
                    remote_url = os.environ.get("MERLIN_REMOTE_MODEL_URL", "").strip()
                    if remote_url:
                        if os.environ.get("MERLIN_REMOTE_MODEL_QUALIFIED") != "1":
                            self._send(503, {"error": "remote_model_not_qualified"})
                            return
                        endpoint, api_key = _remote_model_endpoint()
                    else:
                        if os.environ.get("MERLIN_MODEL_QUALIFIED") != "1":
                            self._send(503, {"error": "model_not_qualified", "detail": "No qualified remote provider or local model is configured."})
                            return
                        endpoint = _loopback_endpoint("MERLIN_MODEL_URL", "http://127.0.0.1:8080/v1/chat/completions")
                        api_key = ""
                    headers = {"Content-Type": "application/json", "Accept": "text/event-stream, application/json"}
                    if api_key:
                        headers["Authorization"] = "Bearer " + api_key
                    request = Request(endpoint, data=raw, headers=headers, method="POST")
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
                            store.append(path, data, {"streamed": True, "bytes": total, "provider_host": urlsplit(endpoint).hostname})
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
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                self._send(400, {"error": "invalid_request", "detail": str(exc)[:300]})
            except (URLError, HTTPError, TimeoutError, OSError) as exc:
                self._send(503, {"error": "local_adapter_unavailable", "detail": str(exc)[:200]})
            except Exception:
                self._send(500, {"error": "internal_error"})

        def log_message(self, fmt: str, *args: Any) -> None:
            # Do not log request bodies, prompts, or voice content.
            return

    return Handler


def serve(port: int = 8765, db_path: str | None = None) -> None:
    target = db_path or os.environ.get(
        "MERLIN_DB_PATH",
        str(Path.home() / ".local" / "share" / "merlin" / "events.sqlite3"),
    )
    store = EventStore(target)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(store))
    print(f"Merlin MVP API listening on http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run the loopback-only Merlin MVP API")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", default=None)
    args = parser.parse_args()
    serve(args.port, args.db)
