"""Bounded build-loop stopping policy over canonical artifact evidence.

The host supplies immutable acceptance criteria and authenticates exact evidence
references. Hashes alone do not authenticate a runner. This gate does not run
models, grant permission, merge, deploy, or claim independent verification.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
import json
import re
from typing import Callable, Mapping
from .artifact_ref import ArtifactRef
from .branch_research import canonical, digest
from .project_registry import MerlinRegistry


@dataclass(frozen=True)
class BuildGoal:
    source_commit: str
    source_map_sha256: str
    software_tests: int
    kernel_cases: int
    max_attempts: int = 3

    def validate(self):
        for value, size in ((self.source_commit, 40), (self.source_map_sha256, 64)):
            if not isinstance(value, str) or re.fullmatch('[0-9a-f]{%d}' % size, value) is None:
                raise ValueError('exact source identity required')
        for value, ceiling in ((self.software_tests, 100000), (self.kernel_cases, 1000), (self.max_attempts, 10)):
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError('strict bounded acceptance count required')


def _strict_counts(report, expected):
    keys = {'tests', 'failures', 'errors', 'skipped'}
    if any(type(report.get(k)) is not int or report[k] < 0 for k in keys):
        return False
    return (report['tests'] == expected and report['failures'] == report['errors'] == report['skipped'] == 0
            and report.get('passed') is True)


def decide_build(goal: BuildGoal, *, publication: Mapping, software: Mapping,
                 kernel: Mapping, attempt: int, previous_failure_sha256: str | None = None):
    """Pure decision on host-authenticated observations, never a model's 'done'.

    Every failed check is retained. Repeating an identical failure stops the loop;
    an attempt ceiling bounds retries even when the failure signature changes.
    """
    goal.validate()
    if type(attempt) is not int or not 1 <= attempt <= goal.max_attempts:
        raise ValueError('attempt must be inside the host-owned budget')
    if previous_failure_sha256 is not None and (not isinstance(previous_failure_sha256, str) or not re.fullmatch('[0-9a-f]{64}', previous_failure_sha256)):
        raise ValueError('previous failure identity required')
    reasons = []
    for label, report in (('publication', publication), ('software', software), ('kernel', kernel)):
        if not isinstance(report, Mapping):
            raise ValueError('typed evidence mapping required')
        if report.get('source_commit') != goal.source_commit or report.get('source_map_sha256') != goal.source_map_sha256:
            reasons.append(label + ':source_mismatch')
        if report.get('qualification') is not False or report.get('promotion_authority') is not False:
            reasons.append(label + ':authority_mismatch')
    if (publication.get('status') != 'observed' or publication.get('readback_complete') is not True
            or publication.get('branch_head') != goal.source_commit):
        reasons.append('publication:unconfirmed')
    if (type(software.get('run_id')) is not int or software['run_id'] < 1
            or software.get('status') != 'succeeded' or not _strict_counts(software, goal.software_tests)):
        reasons.append('software:acceptance_failed')
    cases = kernel.get('cases')
    if (type(kernel.get('run_id')) is not int or kernel['run_id'] < 1
            or kernel.get('status') != 'succeeded' or not isinstance(cases, list)
            or len(cases) != goal.kernel_cases or not all(isinstance(c, dict) for c in cases)
            or not all(isinstance(c.get('name'), str) and c['name'].strip() and c.get('passed') is True for c in cases)
            or len({c['name'] for c in cases if isinstance(c, dict) and isinstance(c.get('name'), str)}) != goal.kernel_cases
            or kernel.get('service_unchanged') is not True):
        reasons.append('kernel:acceptance_failed')
    if kernel.get('run_id') != software.get('run_id'):
        reasons.append('kernel:run_mismatch')
    signature = digest(reasons) if reasons else None
    state = ('ready_for_review' if not reasons else 'stalled' if signature == previous_failure_sha256
             else 'budget_exhausted' if attempt == goal.max_attempts else 'repair_required')
    return {'schema': 'merlin-build-loop-decision/1', 'state': state, 'source_commit': goal.source_commit,
            'source_map_sha256': goal.source_map_sha256, 'attempt': attempt, 'max_attempts': goal.max_attempts,
            'reasons': reasons, 'failure_sha256': signature,
            'automatic_retry': False, 'merge_authorized': False, 'deployment_authorized': False,
            'qualification': False, 'promotion_authority': False}


def record_build_decision(registry: MerlinRegistry, *, project_id: str, goal: BuildGoal,
                          references: Mapping, authenticate: Callable, attempt: int = 1,
                          previous_failure_sha256: str | None = None):
    """Verify/read exact existing artifacts, then persist a content-addressed decision.

    The authenticate callback is an existing host boundary and must return Boolean
    True for the exact role/ref/bytes digest. No signer is manufactured here.
    Attempts are host-admitted; this helper is NOT an autonomous scheduler or a
    tamper-proof global budget ledger. Hermes remains the execution authority.
    """
    if not isinstance(registry, MerlinRegistry) or not callable(authenticate) or set(references) != {'publication', 'software', 'kernel'}:
        raise ValueError('canonical registry and three host-authenticated evidence refs required')
    reports, normalized = {}, {}
    for role, supplied in references.items():
        ref = ArtifactRef.from_mapping(supplied).to_dict()
        if ref['project_id'] != project_id:
            raise ValueError('cross-project build evidence rejected')
        raw = registry.read_artifact_ref(ref, max_bytes=256 * 1024)['content']
        if authenticate(role, deepcopy(ref), ref['sha256']) is not True:
            raise PermissionError('exact build evidence is not authenticated by host')
        report = json.loads(raw)
        if not isinstance(report, dict) or canonical(report).encode() != raw:
            raise ValueError('canonical evidence object required')
        reports[role], normalized[role] = report, ref
    result = decide_build(goal, **reports, attempt=attempt, previous_failure_sha256=previous_failure_sha256)
    result['evidence_refs'] = normalized
    path = 'build-loop-decisions/' + digest(result) + '.json'
    raw = canonical(result).encode()
    old = registry.artifact_history(project_id, path)
    if old:
        if len(old) != 1:
            raise ValueError('immutable build decision has multiple versions')
        ref = registry.artifact_ref(project_id, path, version=1)
        if registry.read_artifact_ref(ref, max_bytes=256 * 1024)['content'] != raw:
            raise ValueError('build decision identity differs')
    else:
        registry.put_artifact(project_id, path, raw, 'application/json')
        ref = registry.artifact_ref(project_id, path, version=1)
    return {**result, 'decision_ref': ref}
