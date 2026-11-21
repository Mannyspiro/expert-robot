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
class SelectedSourceRelation:
    """A selected-file equivalence claim; never a whole-commit or ancestry claim."""

    tested_source_commit: str
    observed_publication_head: str
    source_map_sha256: str
    git_blob_map_sha256: str
    source_files: int

    def to_dict(self):
        return {'schema': 'merlin-selected-source-relation/1',
                'relationship': ('same_commit' if self.tested_source_commit == self.observed_publication_head
                                 else 'identical_selected_files'),
                'tested_source_commit': self.tested_source_commit,
                'observed_publication_head': self.observed_publication_head,
                'source_map_sha256': self.source_map_sha256,
                'git_blob_map_sha256': self.git_blob_map_sha256,
                'source_files': self.source_files,
                'whole_commit_equivalence': False, 'ancestry_verified': False}


@dataclass(frozen=True)
class BuildGoal:
    source_commit: str
    source_map_sha256: str
    software_tests: int
    kernel_cases: int
    max_attempts: int = 3
    software_test_inventory_sha256: str | None = None
    required_kernel_cases: tuple[str, ...] = ()

    def validate(self):
        for value, size in ((self.source_commit, 40), (self.source_map_sha256, 64),
                            (self.software_test_inventory_sha256, 64)):
            if not isinstance(value, str) or re.fullmatch('[0-9a-f]{%d}' % size, value) is None:
                raise ValueError('exact source identity required')
        for value, ceiling in ((self.software_tests, 100000), (self.kernel_cases, 1000), (self.max_attempts, 10)):
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError('strict bounded acceptance count required')
        if (not isinstance(self.required_kernel_cases, tuple)
                or len(self.required_kernel_cases) != self.kernel_cases
                or any(not _case_name(name) for name in self.required_kernel_cases)
                or len(set(self.required_kernel_cases)) != self.kernel_cases):
            raise ValueError('immutable exact required kernel case names are required')


@dataclass(frozen=True)
class BuildGoalV3(BuildGoal):
    """Explicit v3 selection/context contract; existing v2 callers are unchanged."""

    source_files: int = 0
    required_context_cases: tuple[str, ...] = ()

    def validate(self):
        super().validate()
        if type(self.source_files) is not int or not 1 <= self.source_files <= 200:
            raise ValueError('bounded selected source file count required')
        if (not isinstance(self.required_context_cases, tuple)
                or not 1 <= len(self.required_context_cases) <= 1000
                or any(not _case_name(name) for name in self.required_context_cases)
                or len(set(self.required_context_cases)) != len(self.required_context_cases)):
            raise ValueError('immutable exact context case names required')


def checked_publication_relation(goal: BuildGoalV3, publication: Mapping):
    """Check both complete selected manifests without changing the observed head.

    Manifest provenance is authenticated by the host admission boundary. This
    pure check establishes membership/hash equality only, never ancestry,
    equivalence of unselected files, or authenticity from a digest alone.
    """
    goal.validate()
    head = publication.get('branch_head')
    if not isinstance(head, str) or re.fullmatch('[0-9a-f]{40}', head) is None:
        raise ValueError('exact observed publication head required')
    manifests = (publication.get('tested_manifest'), publication.get('published_manifest'))
    for manifest, commit in zip(manifests, (goal.source_commit, head)):
        if not isinstance(manifest, dict) or manifest.get('source_commit') != commit:
            raise ValueError('selected manifest commit differs')
        files, blobs = manifest.get('files'), manifest.get('git_blobs')
        if (not isinstance(files, dict) or not isinstance(blobs, dict)
                or len(files) != goal.source_files or set(files) != set(blobs)):
            raise ValueError('complete selected manifest membership required')
        for name, checksum in files.items():
            if (not isinstance(name, str) or not 0 < len(name) <= 1024
                    or name.startswith('/') or '\\' in name
                    or any(part in ('', '.', '..') for part in name.split('/'))
                    or any(ord(char) < 32 or ord(char) == 127 for char in name)
                    or not isinstance(checksum, str) or re.fullmatch('[0-9a-f]{64}', checksum) is None
                    or not isinstance(blobs[name], str) or re.fullmatch('[0-9a-f]{40}', blobs[name]) is None):
                raise ValueError('normalized path and exact source hashes required')
        if (digest(files) != goal.source_map_sha256
                or manifest.get('source_map_sha256') != goal.source_map_sha256):
            raise ValueError('selected source map differs')
    if (manifests[0]['files'] != manifests[1]['files']
            or manifests[0]['git_blobs'] != manifests[1]['git_blobs']):
        raise ValueError('selected source bytes or Git identities differ')
    return SelectedSourceRelation(goal.source_commit, head, goal.source_map_sha256,
                                  digest(manifests[0]['git_blobs']), goal.source_files).to_dict()


def _check_context(goal, context, software, reject):
    if not isinstance(context, Mapping):
        raise ValueError('typed context evidence mapping required')
    for key, expected in (('source_commit', goal.source_commit), ('source_map_sha256', goal.source_map_sha256),
                          ('qualification', False), ('promotion_authority', False)):
        if (context.get(key) is not expected if type(expected) is bool else context.get(key) != expected):
            reject('context:' + key + '_mismatch', {key: _scalar(context.get(key))})
    cases = context.get('cases')
    bounded = isinstance(cases, list) and len(cases) <= 1000
    names = [row['name'] for row in cases if isinstance(row, dict) and _case_name(row.get('name'))] if bounded else []
    if (not bounded or len(names) != len(cases) or len(set(names)) != len(names)
            or set(names) != set(goal.required_context_cases)):
        reject('context:case_inventory_mismatch', {'case_names': sorted(names)})
    if (context.get('status') != 'succeeded' or context.get('service_unchanged') is not True
            or not bounded or not cases or any(not isinstance(row, dict) or row.get('passed') is not True for row in cases)):
        reject('context:acceptance_failed', {'status': _scalar(context.get('status')),
            'service_unchanged': _scalar(context.get('service_unchanged')),
            'failed_cases': sorted([{'name': row['name'], 'passed': _scalar(row.get('passed'))}
                for row in cases if isinstance(row, dict) and _case_name(row.get('name'))
                and row.get('passed') is not True], key=canonical) if bounded else []})
    if type(context.get('run_id')) is not int or context['run_id'] < 1 or context['run_id'] != software.get('run_id'):
        reject('context:run_mismatch', {'same_run': False})


def decide_build_v3(goal: BuildGoalV3, *, publication: Mapping, software: Mapping,
                    kernel: Mapping, context: Mapping, attempt: int,
                    previous_failure_sha256: str | None = None):
    """Pure v3 policy after host admission, with explicit source relation/context.

    Use build_admission.admit_oci_build for actual run/controller authentication
    and canonical persistence. Calling this pure function grants no authority.
    """
    if not isinstance(goal, BuildGoalV3):
        raise ValueError('explicit v3 goal required')
    return _decide_build(goal, publication=publication, software=software, kernel=kernel,
                         context=context, attempt=attempt, previous_failure_sha256=previous_failure_sha256,
                         version=3)


def _case_name(value):
    return (isinstance(value, str) and 0 < len(value) <= 400 and value == value.strip()
            and not any(ord(c) < 32 or ord(c) == 127 for c in value))


def software_inventory_digest(test_ids):
    """Identity of a complete executed test inventory, independent of run order.

    The host must measure actual executed IDs, including failed/skipped tests;
    source-file hashes and a planned discovery inventory do not establish this.
    This digest authenticates nothing without the existing host evidence check.
    """
    if (not isinstance(test_ids, (list, tuple)) or not 1 <= len(test_ids) <= 100000
            or any(not _case_name(name) for name in test_ids)
            or len(set(test_ids)) != len(test_ids)):
        raise ValueError('complete distinct bounded executed test IDs required')
    return digest({'schema': 'merlin-executed-software-tests/1', 'test_ids': sorted(test_ids)})


def _software_failures(report):
    """Keep failed test identities; absent details cannot prove repeated failure."""
    failures, complete, consistent = {}, True, True
    for count_key, ids_key in (('failures', 'failed_test_ids'), ('errors', 'error_test_ids'),
                              ('skipped', 'skipped_test_ids')):
        count, ids = report.get(count_key), report.get(ids_key)
        if ids is None and type(count) is int and count == 0:
            failures[ids_key] = []
        elif (type(count) is int and 0 <= count <= 100000 and isinstance(ids, list)
              and len(ids) == count and all(_case_name(name) for name in ids)):
            # A test may have multiple failing subtests; preserve multiplicity.
            failures[ids_key] = sorted(ids)
        else:
            failures[ids_key] = None
            complete = False
            if ids is not None:
                consistent = False
    return failures, complete, consistent


def _scalar(value):
    """Bound malformed report observations without serializing arbitrary objects."""
    if type(value) is bool or value is None:
        return value
    if type(value) is int and -100000 <= value <= 100000:
        return value
    if isinstance(value, str) and len(value) <= 400:
        return value
    return {'invalid_type': type(value).__name__}


def _strict_counts(report, expected):
    keys = {'tests', 'failures', 'errors', 'skipped'}
    if any(type(report.get(k)) is not int or report[k] < 0 for k in keys):
        return False
    return (report['tests'] == expected and report['failures'] == report['errors'] == report['skipped'] == 0
            and report.get('passed') is True)


def decide_build(goal: BuildGoal, *, publication: Mapping, software: Mapping,
                 kernel: Mapping, attempt: int, previous_failure_sha256: str | None = None):
    """Pure decision on host-authenticated observations, never a model's 'done'.

    Exact selected checks are mandatory; legacy count-only evidence fails closed.
    Repeating the same normalized failed-check observations stops the loop.
    Missing software failure IDs leave failure identity incomplete, so an
    identical underlying failure is not inferred. The attempt ceiling still
    bounds retries. This is a stopping policy, not a root-cause classifier.
    """
    return _decide_build(goal, publication=publication, software=software, kernel=kernel,
                         attempt=attempt, previous_failure_sha256=previous_failure_sha256)


def _decide_build(goal, *, publication, software, kernel, attempt,
                  previous_failure_sha256=None, context=None, version=2):
    goal.validate()
    if type(attempt) is not int or not 1 <= attempt <= goal.max_attempts:
        raise ValueError('attempt must be inside the host-owned budget')
    if previous_failure_sha256 is not None and (not isinstance(previous_failure_sha256, str) or not re.fullmatch('[0-9a-f]{64}', previous_failure_sha256)):
        raise ValueError('previous failure identity required')
    acceptance = {'schema': 'merlin-build-acceptance/' + str(version), 'source_commit': goal.source_commit,
                  'source_map_sha256': goal.source_map_sha256, 'software_tests': goal.software_tests,
                  'software_test_inventory_sha256': goal.software_test_inventory_sha256,
                  'required_kernel_cases': sorted(goal.required_kernel_cases),
                  'kernel_cases': goal.kernel_cases}
    if version == 3:
        acceptance.update(source_files=goal.source_files,
                          required_context_cases=sorted(goal.required_context_cases),
                          context_cases=len(goal.required_context_cases))
    acceptance_sha256 = digest(acceptance)
    reasons, failed_checks = [], []
    def reject(reason, observations):
        reasons.append(reason)
        failed_checks.append({'check': reason, 'observations': observations})
    for label, report in (('publication', publication), ('software', software), ('kernel', kernel)):
        if not isinstance(report, Mapping):
            raise ValueError('typed evidence mapping required')
        if report.get('source_commit') != goal.source_commit or report.get('source_map_sha256') != goal.source_map_sha256:
            reject(label + ':source_mismatch', {key: _scalar(report.get(key))
                for key in ('source_commit', 'source_map_sha256')})
        if report.get('qualification') is not False or report.get('promotion_authority') is not False:
            reject(label + ':authority_mismatch', {key: _scalar(report.get(key))
                for key in ('qualification', 'promotion_authority')})
    relation = None
    if version == 3:
        try:
            relation = checked_publication_relation(goal, publication)
        except ValueError:
            reject('publication:selected_source_relation_mismatch', {
                'branch_head': _scalar(publication.get('branch_head'))})
    if (publication.get('status') != 'observed' or publication.get('readback_complete') is not True
            or (publication.get('branch_head') != goal.source_commit if version == 2 else relation is None)):
        reject('publication:unconfirmed', {key: _scalar(publication.get(key))
            for key in ('status', 'readback_complete', 'branch_head')})
    if software.get('test_inventory_sha256') != goal.software_test_inventory_sha256:
        reject('software:test_inventory_mismatch', {'test_inventory_sha256':
            _scalar(software.get('test_inventory_sha256'))})
    software_failures, complete_failure_identity, consistent_details = _software_failures(software)
    if not consistent_details:
        reject('software:failure_details_mismatch', software_failures)
    if (type(software.get('run_id')) is not int or software['run_id'] < 1
            or software.get('status') != 'succeeded' or not _strict_counts(software, goal.software_tests)):
        reject('software:acceptance_failed', {
            **{key: _scalar(software.get(key)) for key in ('status', 'tests', 'failures', 'errors', 'skipped', 'passed')},
            'run_id_valid': type(software.get('run_id')) is int and software['run_id'] > 0,
            **software_failures})
    cases = kernel.get('cases')
    bounded_cases = isinstance(cases, list) and len(cases) <= 1000
    names = [c['name'] for c in cases if isinstance(c, dict) and _case_name(c.get('name'))] if bounded_cases else []
    if (not bounded_cases or len(names) != len(cases) or len(names) != goal.kernel_cases
            or len(set(names)) != len(names) or set(names) != set(goal.required_kernel_cases)):
        reject('kernel:case_inventory_mismatch', {'case_names': sorted(names),
            'invalid_entries': len(cases) - len(names) if bounded_cases else 'invalid_or_unbounded_list'})
    if (type(kernel.get('run_id')) is not int or kernel['run_id'] < 1
            or kernel.get('status') != 'succeeded' or not bounded_cases
            or len(cases) != goal.kernel_cases or not all(isinstance(c, dict) for c in cases)
            or not all(isinstance(c.get('name'), str) and c['name'].strip() and c.get('passed') is True for c in cases)
            or len({c['name'] for c in cases if isinstance(c, dict) and isinstance(c.get('name'), str)}) != goal.kernel_cases
            or kernel.get('service_unchanged') is not True):
        case_failures = [{'name': c['name'], 'passed': _scalar(c.get('passed'))}
            for c in cases if isinstance(c, dict) and _case_name(c.get('name')) and c.get('passed') is not True] if bounded_cases else []
        reject('kernel:acceptance_failed', {
            'status': _scalar(kernel.get('status')), 'service_unchanged': _scalar(kernel.get('service_unchanged')),
            'run_id_valid': type(kernel.get('run_id')) is int and kernel['run_id'] > 0,
            'failed_cases': sorted(case_failures, key=canonical)})
    if kernel.get('run_id') != software.get('run_id'):
        reject('kernel:run_mismatch', {'same_run': False})
    if version == 3:
        _check_context(goal, context, software, reject)
    signature = (digest({'schema': 'merlin-build-failure/' + str(version), 'acceptance_sha256': acceptance_sha256,
                         'failed_checks': failed_checks}) if reasons and complete_failure_identity else None)
    state = ('ready_for_review' if not reasons else 'stalled' if signature is not None and signature == previous_failure_sha256
             else 'budget_exhausted' if attempt == goal.max_attempts else 'repair_required')
    result = {'schema': 'merlin-build-loop-decision/' + str(version), 'state': state, 'source_commit': goal.source_commit,
            'source_map_sha256': goal.source_map_sha256, 'attempt': attempt, 'max_attempts': goal.max_attempts,
            'acceptance': acceptance, 'acceptance_sha256': acceptance_sha256,
            'reasons': reasons, 'failed_checks': failed_checks, 'failure_sha256': signature,
            'failure_identity_complete': complete_failure_identity,
            'automatic_retry': False, 'merge_authorized': False, 'deployment_authorized': False,
            'qualification': False, 'promotion_authority': False}
    if version == 3:
        result['publication_relation'] = relation
    return result


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
