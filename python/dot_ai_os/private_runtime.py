"""Private Linux Unix-socket tool host for a fixed, trusted local job route.

No TCP/public listener, OAuth issuer, secret, dynamic import or shell is created.
SO_PEERCRED binds each connection to an operator-allowlisted Linux UID. That UID
is NOT a GitHub workflow identity: a shared runner account must receive only
read-only demo/engineering tools, never mutation authority by default.

The CLI server opens an existing host-published non-WAL registry read-only and
never seeds/imports chat exports. Provision only reviewed engineering/demo
context in a runner-accessible host. A trusted embedding host may register
bounded reviewed low-risk simulation handlers; configuration cannot import code.
Optional pending-only intake requires a separately supplied inbox and an explicit
per-UID grant. It is disabled in the CLI server.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import errno
import json
import os
from pathlib import Path
import re
import socket
import socketserver
import sqlite3
import stat
import struct
import sys
from typing import Any, Callable, Mapping

from merlin.project_registry import MerlinRegistry
from merlin.weight_binding import WeightBinding
from .bridge import DotContextBridge, canonical, digest, text_value
from .dual_coder import DualCoderWorkflow
from .job_inbox import InboxBusy, InboxConflict, ProductionJobInbox

MAX_CALL_BYTES = 32 * 1024
MAX_REPLY_BYTES = 64 * 1024
_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}")
_SESSION = re.compile(r"[A-Za-z0-9_-]{1,100}")


class PrivateHostConfigurationError(ValueError):
    pass


class _WeightBindingUnavailable(PermissionError):
    """An existing bound session has no separately provisioned host binding."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _json(raw: bytes) -> dict[str, Any]:
    def invalid_constant(_):
        raise ValueError("non-finite JSON number")
    value = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=invalid_constant)
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    stack = [(value, 0)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if depth > 16 or nodes > 4000:
            raise ValueError("JSON structure exceeds host bounds")
        if isinstance(item, dict):
            stack.extend((x, depth + 1) for x in item.values())
        elif isinstance(item, list):
            stack.extend((x, depth + 1) for x in item)
    canonical(value)  # Reject overflowing JSON numbers, NaN and Infinity.
    return value


class PrivateReadOnlyRegistry(MerlinRegistry):
    """Canonical read methods, with no initialization/migration/write connection."""
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve(strict=True)
        self.db_path = self.root / "merlin.sqlite3"
        self.blobs = self.root / "blobs" / "sha256"
        if self.db_path.is_symlink() or not self.db_path.is_file() or not self.blobs.is_dir():
            raise PrivateHostConfigurationError("existing canonical registry required")
        self._journal()

    def _journal(self):
        with self.db_path.open("rb") as stream:
            header = stream.read(100)
        if (len(header) != 100 or header[:16] != b"SQLite format 3\x00"
                or header[18:20] != b"\x01\x01"):
            raise PrivateHostConfigurationError("host-published non-WAL SQLite snapshot required")

    def _connect(self):
        self._journal()
        db = sqlite3.connect(self.db_path.as_uri() + "?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA query_only=ON")
        return db

    @staticmethod
    def _deny(*args, **kwargs):
        raise PermissionError("private reader cannot mutate the canonical registry")

    _initialize = _deny
    register_project = _deny
    put_artifact = _deny
    add_claim = _deny
    relate = _deny
    record_capability_qualification = _deny


@dataclass(frozen=True)
class RegisteredTool:
    """Trusted, statically registered low-risk handler; never loaded from a request.

    The handler receives (validated_args, host_principal). It must enforce its
    numeric/domain schema. Top-level keys and serialized sizes are enforced here.
    No plugin is granted to any UID unless that UID's grant names it explicitly.
    """
    handler: Callable[[dict[str, Any], str], Mapping[str, Any]]
    required: frozenset[str]
    optional: frozenset[str] = frozenset()
    max_argument_bytes: int = 8000
    max_result_bytes: int = 48000
    read_only: bool = True

    def __post_init__(self):
        if (not callable(self.handler) or not isinstance(self.required, frozenset)
                or not isinstance(self.optional, frozenset) or self.required & self.optional
                or len(self.required | self.optional) > 32
                or any(not isinstance(x, str) or _NAME.fullmatch(x) is None
                       for x in self.required | self.optional)
                or type(self.max_argument_bytes) is not int or not 1 <= self.max_argument_bytes <= 24000
                or type(self.max_result_bytes) is not int or not 1 <= self.max_result_bytes <= 48000
                or type(self.read_only) is not bool):
            raise PrivateHostConfigurationError("bounded reviewed tool definition required")


def _reply(request_id: Any, *, result: Any = None, error: str | None = None) -> dict[str, Any]:
    value = {"schema": "merlin-private-reply/1", "request_id": request_id,
             "ok": error is None, "qualification": False, "promotion_authority": False}
    value["error" if error else "result"] = {"code": error} if error else result
    return value


class PrivateDispatcher:
    def __init__(self, bridge: DotContextBridge, *, grants: Mapping[int, Mapping[str, Any]],
                 plugin_tools: Mapping[str, RegisteredTool] | None = None,
                 inbox: ProductionJobInbox | None = None,
                 rsi_weight_binding_resolver: Callable[[str], WeightBinding | None] | None = None):
        # Trusted embedding-host injection only. The CLI and request/configuration
        # schemas cannot select a manifest, provider, callback or execution path.
        if rsi_weight_binding_resolver is not None and not callable(rsi_weight_binding_resolver):
            raise PrivateHostConfigurationError("RSI weight binding resolver must be callable or None")
        self.bridge = bridge
        self.inbox = inbox
        self.rsi_weight_binding_resolver = rsi_weight_binding_resolver
        self.tools = self._builtins()
        for name, definition in (plugin_tools or {}).items():
            if (not isinstance(name, str) or _NAME.fullmatch(name) is None or name in self.tools
                    or not isinstance(definition, RegisteredTool) or definition.read_only is not True):
                raise PrivateHostConfigurationError("invalid or shadowed plugin tool")
            self.tools[name] = definition
        if inbox is not None:
            self.tools["job_submit"] = RegisteredTool(
                lambda args, principal: inbox.submit(principal=principal, **args),
                frozenset({"idempotency_key", "request"}), max_argument_bytes=20000, read_only=False)
            self.tools["job_status"] = RegisteredTool(
                lambda args, principal: inbox.status(principal=principal, **args),
                frozenset({"request_id"}))
        if not isinstance(grants, Mapping) or not 1 <= len(grants) <= 32:
            raise PrivateHostConfigurationError("explicit bounded Linux UID grants required")
        self.grants = {}
        for uid, grant in grants.items():
            if (type(uid) is not int or uid < 0 or not isinstance(grant, Mapping)
                    or set(grant) != {"principal", "tools"}):
                raise PrivateHostConfigurationError("UID grant must contain principal and tools")
            principal = text_value(grant["principal"], "host principal", 256)
            if principal != principal.strip() or any(ord(c) < 32 for c in principal):
                raise PrivateHostConfigurationError("canonical host principal required")
            allowed = grant["tools"]
            if (not isinstance(allowed, (list, tuple)) or not allowed
                    or any(not isinstance(x, str) for x in allowed)
                    or len(set(allowed)) != len(allowed) or not set(allowed) <= set(self.tools)):
                raise PrivateHostConfigurationError("grant names must match registered tools; no wildcards")
            self.grants[uid] = {"principal": principal, "tools": tuple(allowed)}

    def _builtins(self) -> dict[str, RegisteredTool]:
        def rsi(args, principal):
            session = args["session_id"]
            if not isinstance(session, str) or _SESSION.fullmatch(session) is None:
                raise ValueError("invalid workflow session")
            workflow = DualCoderWorkflow(self.bridge.registry, project_id=self.bridge.project_id)
            base = workflow._base(session)
            try:
                ref = self.bridge.registry.artifact_ref(self.bridge.project_id, base + "/spec.json", version=1)
            except KeyError:
                return workflow.status(session)
            raw = self.bridge.registry.read_artifact_ref(ref, max_bytes=2 * 1024 * 1024)["content"]
            value = _json(raw)
            refs = value.get("specification", {}).get("context_refs")
            if not isinstance(refs, list) or not 1 <= len(refs) <= 50:
                raise ValueError("invalid workflow context")
            for source_ref in refs:
                self.bridge.fetch(source_ref, length_bytes=4)
            if value.get("schema") == "dot-dual-coder-spec/2":
                # Resolve only after the dispatcher has checked the peer/tool
                # grant and this handler has checked the session/context scope.
                resolver = self.rsi_weight_binding_resolver
                binding = None if resolver is None else resolver(session)
                if binding is None:
                    raise _WeightBindingUnavailable("weight-bound status has no configured host binding")
                for source_ref in refs:
                    self.bridge.fetch(source_ref, length_bytes=4)
                # The existing workflow checks the exact registry object and
                # project, then reauthenticates canonical receipts on every read.
                workflow = DualCoderWorkflow(self.bridge.registry, project_id=self.bridge.project_id,
                                             coder_a_binding=binding)
            result = workflow.status(session)
            # Trusted callbacks may revoke context access while resolving or
            # authenticating. Check the same pinned inputs again at status egress.
            for source_ref in refs:
                self.bridge.fetch(source_ref, length_bytes=4)
            return result

        def search(args, principal):
            budget = args.get("budget_bytes", 14000)
            if type(budget) is not int or budget > 48000:
                raise ValueError("private host packet budget exceeds transport limit")
            return self.bridge.search(**args)

        return {
            "health": RegisteredTool(lambda args, principal: {"service": "merlin-dot-private",
                "transport": "unix", "public_listener": False, "job_execution": "unavailable",
                "principal_sha256": digest(principal.encode()), "qualification": False}, frozenset()),
            "context_status": RegisteredTool(lambda args, principal: self.bridge.status(), frozenset()),
            "context_search": RegisteredTool(search, frozenset({"query"}),
                frozenset({"namespace", "limit", "budget_bytes"})),
            "context_fetch": RegisteredTool(lambda args, principal: self.bridge.fetch(**args),
                frozenset({"source_ref"}), frozenset({"start_byte", "length_bytes"})),
            "session_handoff": RegisteredTool(lambda args, principal: self.bridge.load_handoff(**args),
                frozenset({"session_id"})),
            "rsi_status": RegisteredTool(rsi, frozenset({"session_id"})),
        }

    def call(self, uid: int, request: Mapping[str, Any]) -> dict[str, Any]:
        request_id = None
        try:
            if uid not in self.grants:
                return _reply(None, error="unauthorized_peer")
            if (not isinstance(request, Mapping) or set(request) != {"schema", "request_id", "tool", "arguments"}
                    or request["schema"] != "merlin-private-call/1"):
                raise ValueError("invalid private call envelope")
            request_id = request["request_id"]
            if not isinstance(request_id, str) or _SESSION.fullmatch(request_id) is None:
                request_id = None
                raise ValueError("invalid request correlation ID")
            name = request["tool"]
            if not isinstance(name, str) or name not in self.grants[uid]["tools"]:
                return _reply(request_id, error="tool_not_allowed")
            args = request["arguments"]
            definition = self.tools[name]
            if (not isinstance(args, dict) or not definition.required <= set(args)
                    or not set(args) <= definition.required | definition.optional
                    or len(canonical(args)) > definition.max_argument_bytes):
                raise ValueError("tool argument schema or size rejected")
            status_grant = None
            if name == "rsi_status":
                status_grant = {"principal": self.grants[uid]["principal"],
                                "tools": tuple(self.grants[uid]["tools"])}
            result = definition.handler(args, self.grants[uid]["principal"])
            # This new host callback path checks its original grant at egress;
            # it does not change plugin/intake semantics or claim atomic revocation.
            if status_grant is not None and self.grants.get(uid) != status_grant:
                return _reply(request_id, error="operation_not_permitted")
            if not isinstance(result, Mapping) or len(canonical(result)) > definition.max_result_bytes:
                return _reply(request_id, error="result_exceeds_limit")
            response = _reply(request_id, result=dict(result))
            if len(canonical(response)) > MAX_REPLY_BYTES:
                return _reply(request_id, error="result_exceeds_limit")
            return response
        except InboxBusy:
            return _reply(request_id, error="busy_retry_identical_request")
        except InboxConflict:
            return _reply(request_id, error="request_identity_conflict")
        except (ValueError, TypeError, KeyError, UnicodeError):
            return _reply(request_id, error="invalid_or_unavailable_arguments")
        except _WeightBindingUnavailable:
            return _reply(request_id, error="weight_binding_not_configured")
        except PermissionError:
            return _reply(request_id, error="operation_not_permitted")
        except Exception:
            return _reply(request_id, error="internal_error")


def _receive(sock: socket.socket, maximum: int) -> bytes:
    def exact(length):
        chunks = []
        while length:
            part = sock.recv(length)
            if not part:
                raise ValueError("incomplete private frame")
            chunks.append(part)
            length -= len(part)
        return b"".join(chunks)
    length = struct.unpack("!I", exact(4))[0]
    if not 1 <= length <= maximum:
        raise ValueError("private frame exceeds limit")
    return exact(length)


def _send(sock: socket.socket, value: dict[str, Any]):
    raw = canonical(value)
    if len(raw) > MAX_REPLY_BYTES:
        raw = canonical(_reply(None, error="result_exceeds_limit"))
    sock.sendall(struct.pack("!I", len(raw)) + raw)


def _private_parent(path: Path, *, trusted_owner_uid: int | None = None):
    if not path.is_absolute() or len(os.fsencode(path)) > 100:
        raise PrivateHostConfigurationError("short absolute Unix socket path required")
    parent = path.parent
    metadata = parent.stat()
    if (parent.is_symlink() or not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_mode & 0o022 or metadata.st_uid not in {0, os.geteuid(), trusted_owner_uid}):
        raise PrivateHostConfigurationError("socket parent must be trusted and not group/other writable")


class PrivateUnixServer(socketserver.UnixStreamServer):
    request_queue_size = 8
    def __init__(self, socket_path: str | Path, dispatcher: PrivateDispatcher):
        path = Path(socket_path)
        _private_parent(path)
        if path.exists() or path.is_symlink():
            old = path.lstat()
            if not stat.S_ISSOCK(old.st_mode) or old.st_uid != os.geteuid():
                raise PrivateHostConfigurationError("existing socket path is not an owned socket")
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
                probe.settimeout(0.2)
                try:
                    probe.connect(str(path))
                except OSError as exc:
                    if exc.errno != errno.ECONNREFUSED:
                        raise PrivateHostConfigurationError("cannot safely establish stale socket") from exc
                else:
                    raise PrivateHostConfigurationError("private service is already running")
            path.unlink()
        self.dispatcher = dispatcher
        self.socket_path = path
        mask = os.umask(0o117)  # Socket is 0660 at creation, before any accept.
        try:
            super().__init__(str(path), _PrivateHandler)
        finally:
            os.umask(mask)
        self.socket_identity = (path.stat().st_dev, path.stat().st_ino)

    def server_close(self):
        super().server_close()
        if not hasattr(self, "socket_identity"):
            return
        try:
            metadata = self.socket_path.lstat()
            if (metadata.st_dev, metadata.st_ino) == self.socket_identity:
                self.socket_path.unlink()
        except FileNotFoundError:
            pass


class _PrivateHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(5.0)
        try:
            _, uid, _ = struct.unpack("3i", self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if uid not in self.server.dispatcher.grants:
                _send(self.request, _reply(None, error="unauthorized_peer"))
                return
            try:
                request = _json(_receive(self.request, MAX_CALL_BYTES))
            except (ValueError, UnicodeError, RecursionError):
                _send(self.request, _reply(None, error="invalid_private_frame"))
                return
            _send(self.request, self.server.dispatcher.call(uid, request))
        except (OSError, TimeoutError):
            return


def call_socket(socket_path: str | Path, request: Mapping[str, Any], *, expected_server_uid: int,
                timeout_seconds: float = 20.0) -> dict[str, Any]:
    """Call a fixed local service; verify its kernel-reported UID after connect."""
    path = Path(socket_path)
    if type(expected_server_uid) is not int or expected_server_uid < 0:
        raise PrivateHostConfigurationError("fixed expected server UID required")
    _private_parent(path, trusted_owner_uid=expected_server_uid)
    metadata = path.lstat()
    if (not stat.S_ISSOCK(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)
            or metadata.st_mode & 0o007 or type(expected_server_uid) is not int
            or expected_server_uid < 0 or metadata.st_uid != expected_server_uid):
        raise PrivateHostConfigurationError("private socket identity/permissions rejected")
    raw = canonical(request)
    if not 1 <= len(raw) <= MAX_CALL_BYTES:
        raise ValueError("private call exceeds transport ceiling")
    if type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= 30:
        raise ValueError("client timeout must be bounded")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout_seconds)
        sock.connect(str(path))
        _, uid, _ = struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if uid != expected_server_uid:
            raise PermissionError("connected server identity mismatch")
        sock.sendall(struct.pack("!I", len(raw)) + raw)
        return _json(_receive(sock, MAX_REPLY_BYTES))


def load_configuration(path: str | Path) -> dict[str, Any]:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        metadata = os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o022
                or metadata.st_uid not in {0, os.geteuid()} or metadata.st_size > 16000):
            raise PrivateHostConfigurationError("operator-owned bounded configuration required")
        raw = os.read(descriptor, 16001)
    finally:
        os.close(descriptor)
    config = _json(raw)
    if (set(config) != {"schema", "project_id", "namespaces", "grants"}
            or config["schema"] != "merlin-private-host/1" or not isinstance(config["grants"], list)):
        raise PrivateHostConfigurationError("invalid private host configuration schema")
    grants = {}
    for item in config["grants"]:
        if (not isinstance(item, dict) or set(item) != {"uid", "principal", "tools"}
                or type(item["uid"]) is not int or item["uid"] in grants):
            raise PrivateHostConfigurationError("unique explicit UID grants required")
        grants[item["uid"]] = {"principal": item["principal"], "tools": item["tools"]}
    return {**config, "grants": grants}


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--root", required=True, type=Path)
    serve.add_argument("--socket", required=True, type=Path)
    serve.add_argument("--config", required=True, type=Path)
    serve.add_argument("--simulation-demo", action="store_true",
                       help="Enable the fixed reviewed ideal-DC demo; never import a caller-named module")
    call = sub.add_parser("call")
    call.add_argument("--socket", required=True, type=Path)
    call.add_argument("--server-uid", required=True, type=int)
    args = parser.parse_args()
    if args.command == "call":
        raw = sys.stdin.buffer.read(MAX_CALL_BYTES + 1)
        if len(raw) > MAX_CALL_BYTES:
            parser.error("private call exceeds transport ceiling")
        response = call_socket(args.socket, _json(raw), expected_server_uid=args.server_uid)
        print(json.dumps(response, ensure_ascii=False))
        return 0 if response["ok"] else 1
    config = load_configuration(args.config)
    registry = PrivateReadOnlyRegistry(args.root)
    bridge = DotContextBridge(registry, project_id=config["project_id"], namespaces=config["namespaces"])
    registry.inventory(config["project_id"])
    plugins = {}
    if args.simulation_demo:
        from .research_tools import (reviewed_virtual_circuit_demo, research_contract,
                                     research_episode_demo, mathematical_lenses_demo)
        plugins["virtual_circuit_demo"] = RegisteredTool(
            lambda arguments, principal: reviewed_virtual_circuit_demo(arguments), frozenset(),
            frozenset({"operation"}))
        for name, handler in (("research_contract", research_contract),
                              ("research_episode_demo", research_episode_demo),
                              ("mathematical_lenses_demo", mathematical_lenses_demo)):
            plugins[name] = RegisteredTool(lambda arguments, principal, call=handler: call(arguments), frozenset())
    dispatcher = PrivateDispatcher(bridge, grants=config["grants"], plugin_tools=plugins)
    with PrivateUnixServer(args.socket, dispatcher) as server:
        server.serve_forever(poll_interval=0.5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
