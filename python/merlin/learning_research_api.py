"""Host-authenticated HTTP dispatch for existing LMS research services.

The host resolver alone supplies Actor identity. This adapter issues no token,
fetches no URL, provisions no tenant, and grants no grading/promotion authority.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .artifact_ref import ArtifactRef
from .learning_evidence import LearningEvidenceService
from .learning_lab_bridge import LearningLabBridge
from .learning_platform import Actor, LearningPlatform, LearningPermissionError, LearningConflictError, ROLES


_ROUTE = re.compile(r"/api/learning/courses/([A-Za-z0-9_-]{1,200})/research/(sources|evidence|lab|submit-lab)")
_BASE = {"course_version", "manifest_sha256"}
_FIELDS = {
    "sources": (_BASE | {"sources"}, {"conflicts"}),
    "evidence": (_BASE | {"query"}, {"lesson_id", "limit", "budget_bytes"}),
    "lab": (_BASE | {"lesson_id", "run_id", "prediction"}, set()),
    "submit-lab": (_BASE | {"lesson_id", "run_id", "submission_id", "reflection"}, set()),
}


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _text(value, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError("invalid bounded text")


class LearningResearchAPI:
    MAX_BODY_BYTES = 131072
    MAX_RESPONSE_BYTES = 131072

    def __init__(self, platform: LearningPlatform, evidence_service: LearningEvidenceService | None,
                 identity_resolver: Any | None, lab_bridge: LearningLabBridge | None = None):
        if not isinstance(platform, LearningPlatform):
            raise ValueError("canonical learning platform required")
        if identity_resolver is not None and not callable(identity_resolver):
            raise ValueError("host identity resolver must be callable or absent")
        if evidence_service is not None and not isinstance(evidence_service, LearningEvidenceService):
            raise ValueError("canonical evidence service required")
        if lab_bridge is not None and not isinstance(lab_bridge, LearningLabBridge):
            raise ValueError("canonical lab bridge required")
        self.platform = platform; self.evidence_service = evidence_service
        self.identity_resolver = identity_resolver; self.lab_bridge = lab_bridge
        self._validate_configuration()

    @property
    def registry(self):
        if self.evidence_service is not None:
            return self.evidence_service.registry
        return self.lab_bridge.evidence.registry if self.lab_bridge is not None else None

    def _validate_configuration(self):
        services = [service for service in (self.evidence_service, self.lab_bridge) if service is not None]
        if any(service.platform is not self.platform for service in services):
            raise ValueError("research services must share the exact platform")
        if self.evidence_service is not None and self.lab_bridge is not None:
            if (self.evidence_service.registry is not self.lab_bridge.evidence.registry
                    or _canonical(self.evidence_service.tenant_projects) != _canonical(self.lab_bridge.tenant_projects)):
                raise ValueError("research services must share exact registry and tenant provisioning")

    @staticmethod
    def matches_path(path):
        return isinstance(path, str) and _ROUTE.fullmatch(path) is not None

    @staticmethod
    def _bounded_body(data):
        if type(data) is not dict:
            raise ValueError("object required")
        stack = [(data, 0)]; count = 0
        while stack:
            value, depth = stack.pop(); count += 1
            if count > 4096 or depth > 16:
                raise ValueError("body structure exceeds limits")
            if isinstance(value, dict):
                if any(not isinstance(key, str) for key in value):
                    raise ValueError("text keys required")
                stack.extend((item, depth + 1) for item in value.values())
            elif isinstance(value, list):
                stack.extend((item, depth + 1) for item in value)
        if len(_canonical(data)) > LearningResearchAPI.MAX_BODY_BYTES:
            raise ValueError("body exceeds byte limit")
        return data

    @staticmethod
    def decode_body(raw):
        """Strict standard JSON decoding for this route family only."""
        if not isinstance(raw, bytes) or not 1 <= len(raw) <= LearningResearchAPI.MAX_BODY_BYTES:
            raise ValueError("invalid body size")
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError("duplicate field")
                result[key] = value
            return result
        def invalid(_):
            raise ValueError("nonfinite number")
        return LearningResearchAPI._bounded_body(json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid))

    @staticmethod
    def _error(status, code):
        return status, {"error": code, "qualification": False, "promotion_authority": False, "mastery_updated": False}

    def _actor(self, headers):
        try:
            actor = self.identity_resolver(headers)
            if type(actor) is not Actor or actor.role not in ROLES:
                return None
            for value in (actor.tenant_id, actor.actor_id):
                _text(value, 200)
                if value != value.strip() or any(ord(char) < 32 for char in value):
                    return None
            return actor
        except Exception:
            return None

    @staticmethod
    def _arguments(operation, data):
        LearningResearchAPI._bounded_body(data)
        required, optional = _FIELDS[operation]
        if not required <= set(data) or not set(data) <= required | optional:
            raise ValueError("request field set rejected")
        version = data["course_version"]
        if type(version) is not int or not 1 <= version <= 1000000:
            raise ValueError("invalid exact version")
        if not isinstance(data["manifest_sha256"], str) or re.fullmatch(r"[0-9a-f]{64}", data["manifest_sha256"]) is None:
            raise ValueError("invalid exact manifest digest")
        for name, maximum in (("lesson_id", 100), ("run_id", 120), ("submission_id", 120),
                              ("query", 1000), ("prediction", 2000), ("reflection", 4000)):
            if name in data and not (name == "lesson_id" and operation == "evidence" and data[name] is None):
                _text(data[name], maximum)
        for name, low, high in (("limit", 1, 30), ("budget_bytes", 2000, 64000)):
            if name in data and (type(data[name]) is not int or not low <= data[name] <= high):
                raise ValueError("invalid response ceiling")
        return dict(data)

    def dispatch(self, path, headers, data):
        """Return an HTTP status/payload only for the four exact research paths."""
        match = _ROUTE.fullmatch(path) if isinstance(path, str) else None
        if match is None:
            return None
        if self.identity_resolver is None:
            return self._error(503, "research_identity_unconfigured")
        actor = self._actor(headers)
        if actor is None:
            return self._error(401, "research_authentication_required")
        course_id, operation = match.groups()
        service = self.evidence_service if operation in {"sources", "evidence"} else self.lab_bridge
        if service is None:
            return self._error(503, "research_service_unavailable")
        roles = {"instructor", "tenant_admin"} if operation == "sources" else {"learner"}
        if actor.role not in roles:
            return self._error(403, "research_scope_forbidden")
        try:
            self._validate_configuration()
        except Exception:
            return self._error(503, "research_service_unavailable")
        try:
            arguments = self._arguments(operation, data)
        except Exception:
            return self._error(400, "invalid_research_request")
        project = service.tenant_projects.get(actor.tenant_id)
        if project is None:
            return self._error(403, "research_scope_forbidden")
        try:
            # Distinguish missing/inaccessible course scope from missing pinned
            # evidence after authorization, without disclosing either identity.
            self.platform.get_course(actor, course_id, version=arguments["course_version"])
        except (KeyError, PermissionError):
            return self._error(403, "research_scope_forbidden")
        except Exception:
            return self._error(503, "research_integrity_unavailable")
        try:
            if operation == "sources":
                if not isinstance(arguments["sources"], list):
                    raise ValueError("source list required")
                for source in arguments["sources"]:
                    if not isinstance(source, dict) or set(source) != {"resource_id", "record_ref", "source_ref", "review_note"}:
                        raise ValueError("exact source object fields required")
                    for key in ("record_ref", "source_ref"):
                        if ArtifactRef.from_mapping(source[key]).project_id != project:
                            return self._error(403, "research_scope_forbidden")
                result = service.provision_course_sources(actor, course_id=course_id, **arguments)
            elif operation == "evidence":
                result = service.retrieve(actor, course_id=course_id, **arguments)
            elif operation == "lab":
                result = service.run_titan_lab(actor, course_id=course_id, **arguments)
            else:
                result = service.submit_lab_assessment(actor, course_id=course_id, **arguments)
            if (not isinstance(result, dict) or any(result.get(key, False) is not False for key in
                    ("qualification", "promotion_authority", "mastery_updated", "proof_qualified"))
                    or len(_canonical(result)) > self.MAX_RESPONSE_BYTES):
                return self._error(503, "research_integrity_unavailable")
            return 200, {"qualification": False, "promotion_authority": False, "mastery_updated": False, **result}
        except (LearningPermissionError, PermissionError):
            return self._error(403, "research_scope_forbidden")
        except LearningConflictError:
            return self._error(409, "research_conflict")
        except (ValueError, TypeError):
            return self._error(400, "invalid_research_request")
        except Exception:
            return self._error(503, "research_integrity_unavailable")


__all__ = ["LearningResearchAPI"]
