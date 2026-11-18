"""Host-owned opt-in evidence service configuration; no tenant provisioning.

MERLIN_LEARNING_RESEARCH_TENANT_PROJECTS is a bounded JSON tenant-to-existing-
project map. Absent/blank disables automatic composition. A configured map
requires the host's exact canonical stores and callable authenticated resolver.
This module creates no projects, actors, courses, source snapshots or lab bridge.
It supplies no OIDC verifier and never parses credentials or fetches URLs.
"""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import os
from typing import Any, Mapping

from .learning_evidence import LearningEvidenceService
from .learning_platform import LearningPlatform
from .learning_research_api import LearningResearchAPI
from .project_registry import MerlinRegistry

ENVIRONMENT_KEY = 'MERLIN_LEARNING_RESEARCH_TENANT_PROJECTS'


def _mapping(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or not 1 <= len(value) <= 128:
        raise ValueError('learning research requires a bounded tenant-project map')
    for tenant, project in value.items():
        for text, maximum in ((tenant, 200), (project, 120)):
            if (not isinstance(text, str) or not text or text != text.strip() or len(text) > maximum
                    or any(ord(char) < 32 or ord(char) == 127 for char in text)):
                raise ValueError('learning research tenant/project identity is invalid')
    if len(set(value.values())) != len(value):
        raise ValueError('learning research tenants require distinct projects')
    return dict(value)


def learning_research_projects_from_environment(
        environment: Mapping[str, str] | None = None) -> dict[str, str] | None:
    """Parse only non-secret host deployment configuration, never request data."""
    environment = os.environ if environment is None else environment
    raw = environment.get(ENVIRONMENT_KEY, '')
    if not isinstance(raw, str):raise ValueError('invalid learning research configuration')
    if not raw.strip():return None
    if len(raw.encode('utf-8')) > 65536:raise ValueError('learning research configuration exceeds byte limit')
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:raise ValueError('duplicate learning research configuration key')
            value[key] = item
        return value
    try:
        value = json.loads(raw, object_pairs_hook=pairs)
        return _mapping(value)
    except (TypeError, ValueError, RecursionError):
        raise ValueError('invalid learning research tenant-project configuration') from None


def require_existing_learning_database(path: Path) -> None:
    """Inspect the provisioned LMS before any other store can initialize its path."""
    message = 'configured learning research requires an existing LMS database'
    if not path.is_file():
        raise ValueError(message)
    required_tables = {'learning_courses', 'learning_course_versions', 'learning_enrollments'}
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    except sqlite3.Error as exc:
        raise ValueError(message) from exc
    if not required_tables <= tables:
        raise ValueError(message)


def build_learning_research_api(*, platform: LearningPlatform, registry: MerlinRegistry,
        identity_resolver: Any, tenant_projects: Mapping[str, str]) -> LearningResearchAPI:
    """Compose existing services, preserving exact store and resolver identities.

    Caller-provided resolvers remain responsible for actual authentication. An
    unconfigured OIDC resolver is rejected; no alternate identity is fabricated.
    Missing projects fail before any new project/source/course is registered.
    """
    if not isinstance(tenant_projects, Mapping):
        raise ValueError('host-owned tenant-project mapping required')
    projects = _mapping(dict(tenant_projects))
    if not isinstance(platform, LearningPlatform) or not isinstance(registry, MerlinRegistry):
        raise ValueError('configured learning research requires existing canonical stores')
    if not callable(identity_resolver) or getattr(identity_resolver, 'configured', True) is not True:
        raise ValueError('configured learning research requires an authenticated host resolver')
    for project in projects.values():
        try:registry.inventory(project)
        except KeyError:raise ValueError('configured learning research project is unavailable') from None
    service = LearningEvidenceService(platform, registry, tenant_projects=projects)
    return LearningResearchAPI(platform, service, identity_resolver)


__all__ = ['ENVIRONMENT_KEY', 'learning_research_projects_from_environment', 'build_learning_research_api']
