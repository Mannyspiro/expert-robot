"""Bounded, principal-scoped request intake over Merlin's canonical registry.

The trusted host supplies authenticated principal identity and an explicit
namespace allowlist. Model/request JSON cannot grant approval or authority.
Accepted requests remain pending_operator_review; no callback, model, network,
shell, Hermes enqueue, runner, signing, verification or promotion is invoked.

One immutable global key binding and one immutable principal-scoped request
artifact are stored in the existing registry. Binding is committed first;
identical retry can finish an interrupted local write without reassigning a key.
No second task database/ledger is created. Global keys must be unique across
principals within the project; clients should generate opaque random keys.

Linux advisory locking coordinates cooperating writers with DualCoderWorkflow
using its existing registry-wide lock filename. It does not constrain unrelated
writers, compromised hosts or external process/resource use. Durability is the
canonical registry's SQLite/blob durability, not a separate production guarantee.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import math
import os
import re
import stat
import time
from typing import Any, Mapping

from merlin.artifact_ref import ArtifactRef
from merlin.project_registry import MerlinRegistry

from .bridge import DotContextBridge, canonical, digest, text_value

MAX_CONTEXT_REFS = 20
MAX_CONTEXT_BYTES = 128 * 1024
MAX_REQUEST_BYTES = 16 * 1024
_FIELDS = frozenset({"namespace", "objective", "source_commit", "source_refs",
                     "acceptance_criteria", "max_cost_usd"})
_SHA = re.compile(r"[0-9a-f]{64}")


class InboxConflict(ValueError):
    """An immutable key/request identity conflicts with the requested operation."""


class InboxBusy(RuntimeError):
    """Another cooperative registry writer exceeded this intake's bounded wait."""


def _principal_digest(principal: Any) -> str:
    text_value(principal, "runtime principal", 256)
    if (principal != principal.strip() or len(principal.encode("utf-8")) > 1024
            or any(ord(char) < 32 or ord(char) == 127 for char in principal)):
        raise ValueError("runtime principal must be a canonical non-control identifier")
    return digest(principal.encode("utf-8"))


def _key_digest(key: Any) -> str:
    if not isinstance(key, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}", key) is None:
        raise ValueError("idempotency key must be a bounded opaque ASCII identifier")
    return digest(key.encode("ascii"))


class ProductionJobInbox:
    def __init__(self, registry: MerlinRegistry, *, namespaces: tuple[str, ...],
                 project_id: str = "dot-ai-os", lock_timeout_seconds: float = 5.0):
        self.registry = registry
        self.project_id = text_value(project_id, "project_id", 120)
        self.bridge = DotContextBridge(registry, project_id=project_id, namespaces=namespaces)
        if (type(lock_timeout_seconds) not in (int, float) or not math.isfinite(lock_timeout_seconds)
                or not 0 < lock_timeout_seconds <= 5):
            raise ValueError("lock wait must be finite and between 0 and 5 seconds")
        self.lock_timeout_seconds = float(lock_timeout_seconds)
        # A request path may not implicitly provision a project or alter its metadata.
        self.registry.inventory(self.project_id)

    @contextmanager
    def _locked(self):
        # Shared with DualCoderWorkflow; legacy filename, registry-wide scope.
        path = self.registry.root / "dot-dual-coder.lock"
        flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
        descriptor = os.open(path, flags, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise InboxConflict("cooperative registry lock is not a regular file")
            deadline = time.monotonic() + self.lock_timeout_seconds
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError as exc:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise InboxBusy("registry writer is busy; retry the identical request later") from exc
                    time.sleep(min(0.01, remaining))
            yield
        finally:
            os.close(descriptor)

    def _read_once(self, path: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
        history = self.registry.artifact_history(self.project_id, path)
        if not history:
            return None
        if len(history) != 1:
            raise InboxConflict("immutable inbox artifact has multiple versions")
        ref = self.registry.artifact_ref(self.project_id, path, version=1)
        raw = self.registry.read_artifact_ref(ref, max_bytes=MAX_REQUEST_BYTES)["content"]
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise InboxConflict("invalid inbox record") from exc
        if not isinstance(payload, dict) or canonical(payload) != raw:
            raise InboxConflict("inbox record is not a canonical object")
        return payload, ref

    def _put_once(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        old = self._read_once(path)
        if old is not None:
            if canonical(old[0]) != canonical(payload):
                raise InboxConflict("immutable inbox identity conflicts with existing record")
            return old[1]
        self.registry.put_artifact(self.project_id, path, canonical(payload), "application/json")
        return self.registry.artifact_ref(self.project_id, path, version=1)

    def _request(self, value: Any) -> tuple[dict[str, Any], int]:
        if not isinstance(value, Mapping) or set(value) != _FIELDS:
            raise ValueError("request must contain exactly the declared intake fields")
        namespace = self.bridge._namespace(value["namespace"])
        objective = text_value(value["objective"], "objective", 2000)
        commit = value["source_commit"]
        if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
            raise ValueError("source_commit requires a full lowercase Git commit")
        cost = value["max_cost_usd"]
        if type(cost) is not int or cost != 0:
            raise ValueError("max_cost_usd must be exactly integer zero")
        criteria = value["acceptance_criteria"]
        if not isinstance(criteria, list) or not 1 <= len(criteria) <= 20:
            raise ValueError("1 through 20 acceptance criteria required")
        for item in criteria:
            text_value(item, "acceptance criterion", 1000)
        refs = value["source_refs"]
        if not isinstance(refs, list) or not 1 <= len(refs) <= MAX_CONTEXT_REFS:
            raise ValueError("1 through 20 exact context references required")
        normalized_refs = []
        seen = set()
        for value_ref in refs:
            ref = ArtifactRef.from_mapping(value_ref).to_dict()
            identity = canonical(ref)
            if identity in seen:
                raise ValueError("duplicate context references are not admitted")
            seen.add(identity)
            normalized_refs.append(ref)
        request = {"namespace": namespace, "objective": objective, "source_commit": commit,
                   "source_refs": normalized_refs, "acceptance_criteria": list(criteria),
                   "max_cost_usd": 0}
        if len(canonical(request)) > MAX_REQUEST_BYTES:
            raise ValueError("request exceeds 16 KiB serialized ceiling")
        total = 0
        for ref in normalized_refs:
            # Public fetch validates exact project/path/namespace/digest and UTF-8.
            # Four bytes suffice for the first Unicode scalar; no source body is
            # returned or persisted in the inbox metadata.
            page = self.bridge.fetch(ref, length_bytes=4)
            size = page["total_bytes"]
            if type(size) is not int or size < 1:
                raise ValueError("context sources must be nonempty")
            total += size
            if total > MAX_CONTEXT_BYTES:
                raise ValueError("context exceeds 128 KiB; select a smaller pinned context shard")
        return request, total

    @staticmethod
    def _request_path(principal_sha: str, request_id: str) -> str:
        return f"job-inbox/principals/{principal_sha}/requests/{request_id}.json"

    @staticmethod
    def _binding_path(key_sha: str) -> str:
        return f"job-inbox/idempotency/{key_sha}.json"

    def _envelope(self, *, principal_sha: str, key_sha: str,
                  request: dict[str, Any], total: int) -> dict[str, Any]:
        result = {"schema": "dot-production-job-request/1", "principal_sha256": principal_sha,
                  "idempotency_key_sha256": key_sha, "request": request,
                  "context_total_bytes": total, "state": "pending_operator_review",
                  "execution_state": "not_dispatched", "approval_state": "not_requested",
                  "qualification": False, "promotion_authority": False}
        if len(canonical(result)) > MAX_REQUEST_BYTES:
            raise ValueError("complete request envelope exceeds 16 KiB ceiling")
        return result

    def submit(self, *, principal: str, idempotency_key: str,
               request: Mapping[str, Any]) -> dict[str, Any]:
        """Persist one bounded request or return its exact idempotent replay.

        Principal identity must be supplied by the authenticated host, outside
        request JSON. No execution/readiness/approval field is accepted.
        """
        principal_sha = _principal_digest(principal)
        key_sha = _key_digest(idempotency_key)
        with self._locked():
            self.registry.inventory(self.project_id)
            binding_path = self._binding_path(key_sha)
            old_binding = self._read_once(binding_path)
            try:
                normalized, total = self._request(request)
                envelope = self._envelope(principal_sha=principal_sha, key_sha=key_sha,
                                          request=normalized, total=total)
            except ValueError as exc:
                if old_binding is not None:
                    raise InboxConflict("idempotency key cannot be reused for an altered or invalid request") from exc
                raise
            request_id = digest(canonical(envelope))
            binding = {"schema": "dot-job-idempotency-binding/1", "principal_sha256": principal_sha,
                       "idempotency_key_sha256": key_sha, "request_id": request_id}
            if old_binding is not None and canonical(old_binding[0]) != canonical(binding):
                raise InboxConflict("idempotency key is already bound to a different request identity")
            # Reserve first. An interrupted local write may be safely completed
            # on identical replay, but no other principal/payload can take its key.
            self._put_once(binding_path, binding)
            request_ref = self._put_once(self._request_path(principal_sha, request_id), envelope)
            return self._view(envelope, request_id, request_ref)

    @staticmethod
    def _view(envelope: dict[str, Any], request_id: str,
              request_ref: dict[str, Any]) -> dict[str, Any]:
        return {"schema": "dot-production-job-status/1", "request_id": request_id,
                "request_ref": request_ref, "principal_scoped": True,
                "request": envelope["request"], "context_total_bytes": envelope["context_total_bytes"],
                "state": "pending_operator_review", "execution_state": "not_dispatched",
                "approval_state": "not_requested", "qualification": False,
                "promotion_authority": False,
                "next_gate": "explicit_operator_review_and_existing_Hermes_MCFC_CACE_policy"}

    def status(self, *, principal: str, request_id: str) -> dict[str, Any]:
        """Read one exact caller-scoped request, revalidating all source refs.

        No arbitrary registry listing, other-principal lookup or source text is
        returned. A narrower namespace policy may reject an older stored request.
        """
        principal_sha = _principal_digest(principal)
        if not isinstance(request_id, str) or _SHA.fullmatch(request_id) is None:
            raise ValueError("request_id requires a full lowercase digest")
        self.registry.inventory(self.project_id)
        saved = self._read_once(self._request_path(principal_sha, request_id))
        if saved is None:
            raise KeyError("no request found in caller scope")
        envelope, ref = saved
        fields = {"schema", "principal_sha256", "idempotency_key_sha256", "request",
                  "context_total_bytes", "state", "execution_state", "approval_state",
                  "qualification", "promotion_authority"}
        if (set(envelope) != fields or envelope["schema"] != "dot-production-job-request/1"
                or envelope["principal_sha256"] != principal_sha
                or not isinstance(envelope["idempotency_key_sha256"], str)
                or _SHA.fullmatch(envelope["idempotency_key_sha256"]) is None
                or envelope["state"] != "pending_operator_review"
                or envelope["execution_state"] != "not_dispatched"
                or envelope["approval_state"] != "not_requested"
                or envelope["qualification"] is not False or envelope["promotion_authority"] is not False
                or digest(canonical(envelope)) != request_id):
            raise InboxConflict("invalid immutable request envelope")
        request, total = self._request(envelope["request"])
        expected = self._envelope(principal_sha=principal_sha, key_sha=envelope["idempotency_key_sha256"],
                                  request=request, total=total)
        if canonical(expected) != canonical(envelope):
            raise InboxConflict("request metadata or context size binding mismatch")
        expected_binding = {"schema": "dot-job-idempotency-binding/1", "principal_sha256": principal_sha,
                            "idempotency_key_sha256": envelope["idempotency_key_sha256"],
                            "request_id": request_id}
        binding = self._read_once(self._binding_path(envelope["idempotency_key_sha256"]))
        if binding is None or canonical(binding[0]) != canonical(expected_binding):
            raise InboxConflict("request has no exact immutable key binding")
        return self._view(envelope, request_id, ref)
