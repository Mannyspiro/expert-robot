"""Host entry point for exact OCI evidence admission into the existing registry.

No network, credentials, provider calls, execution, promotion or service wiring
is provided here. A provisioned host must authenticate every exact detached
reference/digest against its own custody and observations. A digest is identity,
not authentication. Native input JSON stays in its original byte representation.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import io
import json
import re
from typing import Callable, Mapping
import zipfile

from .artifact_ref import ArtifactRef
from .branch_research import canonical, digest
from .build_loop import (BuildGoalV3, checked_publication_relation, decide_build_v3,
                         software_inventory_digest)
from .project_registry import MerlinRegistry


KERNEL_CASES = (
    'aggregate_memory_limit', 'cpu_time_limit', 'detached_descendant_cleanup',
    'fixed_program_and_actual_kernel_limits', 'inet_socket_creation_denied',
    'manager_wall_deadline', 'revoked_authorization_stops_unit', 'tasks_max_fork_denial',
)
CONTEXT_CASES = (
    'acknowledgement_loss_after_real_process',
    'actual_cancellation_stops_process_and_fences_successor',
    'completed_process_checker_recovery_without_relaunch',
    'context_restart_actual_worker_process_and_duplicate_replay',
    'non_boolean_host_authority_cannot_start_process',
    'wrong_output_cannot_pass_or_advance_dependency',
)
EVIDENCE_ROLES = frozenset({
    'publication', 'tested_manifest', 'published_manifest', 'run', 'artifact_metadata',
    'archive', 'report', 'controller_identity', 'controller', 'workflow',
})
_MAX_JSON = 1024 * 1024
_MAX_ARCHIVE = 8 * 1024 * 1024


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _git(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def _hex(value, size):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{%d}' % size, value) is not None


def _text(value, limit=400):
    return (isinstance(value, str) and 0 < len(value) <= limit and value == value.strip()
            and not any(ord(char) < 32 or ord(char) == 127 for char in value))


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _require(condition, message):
    if not condition:
        raise ValueError(message)


@dataclass(frozen=True)
class OCIAdmissionPolicy:
    """Host-frozen expected identities, separate from claims in downloaded data."""

    source_repository: str
    publication_branch: str
    publication_head: str
    workflow_repository: str
    workflow_branch: str
    workflow_path: str
    workflow_commit: str
    workflow_git_blob: str
    workflow_sha256: str
    controller_git_blob: str
    controller_sha256: str
    run_id: int
    run_attempt: int
    runner: str
    artifact_id: int
    artifact_name: str
    artifact_sha256: str
    artifact_bytes: int

    def validate(self):
        for name in ('source_repository', 'workflow_repository'):
            _require(isinstance(getattr(self, name), str)
                     and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', getattr(self, name)),
                     'exact repository required')
        for name in ('publication_branch', 'workflow_branch', 'runner', 'artifact_name'):
            _require(_text(getattr(self, name)), 'bounded immutable identity required')
        _require(_text(self.workflow_path) and self.workflow_path.startswith('.github/workflows/')
                 and self.workflow_path.endswith(('.yml', '.yaml'))
                 and '\\' not in self.workflow_path
                 and not any(part in ('', '.', '..') for part in self.workflow_path.split('/')),
                 'exact normalized workflow path required')
        for name in ('publication_head', 'workflow_commit', 'workflow_git_blob', 'controller_git_blob'):
            _require(_hex(getattr(self, name), 40), 'exact Git identity required')
        for name in ('workflow_sha256', 'controller_sha256', 'artifact_sha256'):
            _require(_hex(getattr(self, name), 64), 'exact byte digest required')
        _require(_integer(self.run_id, 1, 2**63 - 1) and _integer(self.artifact_id, 1, 2**63 - 1)
                 and _integer(self.run_attempt, 1, 1000)
                 and _integer(self.artifact_bytes, 1, _MAX_ARCHIVE), 'bounded strict run/artifact identity required')
        _require(self.artifact_name == 'merlin-egm-%d-%d' % (self.run_id, self.run_attempt),
                 'artifact name must bind exact run and attempt')


def _json_object(raw, *, canonical_required=False):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, 'duplicate JSON key rejected')
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError('non-finite JSON number rejected')

    try:
        result = json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=invalid_constant)
        _require(isinstance(result, dict), 'JSON object required')
        normalized = canonical(result).encode('utf-8')
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('bounded UTF-8 JSON object required') from exc
    _require(not canonical_required or normalized == raw, 'canonical host envelope required')
    return result


def _no_authority(value):
    _require(value.get('qualification') is False and value.get('promotion_authority') is False,
             'evidence cannot confer qualification or promotion authority')


def _zip_members(raw, *, limit, count):
    """Inspect bounded ZIP bytes in memory; never extract or execute a member."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            rows = archive.infolist()
            _require(1 <= len(rows) <= count, 'archive membership ceiling exceeded')
            _require(sum(row.file_size for row in rows) <= limit, 'archive expansion ceiling exceeded')
            members = {}
            for row in rows:
                name = row.filename
                _require(_text(name, 1024) and not name.startswith('/') and '\\' not in name
                         and not any(part in ('', '.', '..') for part in name.split('/'))
                         and name not in members and not row.is_dir() and not (row.flag_bits & 1)
                         and row.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                         and ((row.external_attr >> 16) & 0o170000) in (0, 0o100000),
                         'normalized distinct regular unencrypted archive members required')
                body = archive.read(row)
                _require(len(body) == row.file_size, 'archive member length differs')
                members[name] = body
            return members
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise ValueError('invalid bounded evidence archive') from exc


def _check_provider(policy, reports, raw):
    run = reports['run']
    _require(type(run.get('id')) is int and run['id'] == policy.run_id
             and type(run.get('run_attempt')) is int and run['run_attempt'] == policy.run_attempt
             and run.get('head_sha') == policy.workflow_commit and run.get('path') == policy.workflow_path
             and run.get('head_branch') == policy.workflow_branch
             and run.get('status') == 'completed' and run.get('conclusion') in ('success', 'failure'),
             'provider run/attempt/workflow observation differs')
    repo = run.get('repository')
    _require(isinstance(repo, dict) and repo.get('full_name') == policy.workflow_repository
             and _integer(repo.get('id'), 1, 2**63 - 1), 'provider repository differs')
    entries = reports['artifact_metadata'].get('artifacts')
    _require(isinstance(entries, list) and 1 <= len(entries) <= 100, 'bounded artifact listing required')
    selected = [entry for entry in entries if isinstance(entry, dict) and entry.get('id') == policy.artifact_id]
    _require(len(selected) == 1, 'exact one artifact identity required')
    item = selected[0]
    _require(type(item.get('id')) is int and item.get('name') == policy.artifact_name
             and type(item.get('size_in_bytes')) is int and item['size_in_bytes'] == policy.artifact_bytes
             and item.get('digest') == 'sha256:' + policy.artifact_sha256 and item.get('expired') is False,
             'provider artifact identity differs')
    bound_run = item.get('workflow_run')
    _require(isinstance(bound_run, dict) and type(bound_run.get('id')) is int
             and bound_run['id'] == policy.run_id and bound_run.get('head_sha') == policy.workflow_commit
             and bound_run.get('head_branch') == policy.workflow_branch
             and type(bound_run.get('repository_id')) is int and bound_run['repository_id'] == repo['id']
             and type(bound_run.get('head_repository_id')) is int and bound_run['head_repository_id'] == repo['id'],
             'artifact belongs to another run/repository/workflow')
    _require(len(raw['archive']) == policy.artifact_bytes and _sha(raw['archive']) == policy.artifact_sha256,
             'actual archive bytes differ')
    for role in ('workflow', 'controller'):
        _require(_sha(raw[role]) == getattr(policy, role + '_sha256')
                 and _git(raw[role]) == getattr(policy, role + '_git_blob'),
                 role + ' actual bytes differ')
    identity = reports['controller_identity']
    _require(identity.get('git_blob') == policy.controller_git_blob
             and identity.get('sha256') == policy.controller_sha256
             and type(identity.get('bytes')) is int and identity['bytes'] == len(raw['controller'])
             and identity.get('workflow_commit') == policy.workflow_commit,
             'controller identity differs from exact workflow/run')


def _check_archive(goal, reports, raw):
    members = _zip_members(raw['archive'], limit=16 * 1024 * 1024, count=40)
    for role, name in (('report', 'report.json'), ('tested_manifest', 'source-manifest.json'),
                       ('controller_identity', 'controller-identity.json'), ('controller', 'controller.txt')):
        _require(members.get(name) == raw[role], 'detached ' + role + ' is not the exact archive member')
    package = members.get('tested-source.zip')
    _require(isinstance(package, bytes) and _sha(package) == reports['report'].get('source_package_sha256'),
             'tested source package identity differs')
    source = _zip_members(package, limit=5 * 1024 * 1024, count=201)
    _require(source.pop('manifest.json', None) == raw['tested_manifest'], 'inner source manifest differs')
    manifest = reports['tested_manifest']
    _require(set(source) == set(manifest['files']) and len(source) == goal.source_files,
             'actual tested source membership differs')
    for name, content in source.items():
        _require(_sha(content) == manifest['files'][name] and _git(content) == manifest['git_blobs'][name],
                 'actual tested source bytes differ: ' + name)
    return members


def _measurement_object(members, name):
    raw = members.get(name)
    _require(isinstance(raw, bytes) and 0 < len(raw) <= 4 * 1024 * 1024,
             'bounded retained measurement required: ' + name)
    return _json_object(raw)


def _check_measurements(goal, report, members):
    """Cross-check retained observations, without recreating kernel semantics."""
    software = report['tests']
    measured = _measurement_object(members, 'software-report.json')
    _require(canonical(measured) == canonical(software), 'raw software report contradicts normalized report')
    events = members.get('software-report.events.txt')
    _require(isinstance(events, bytes) and 0 < len(events) <= 4 * 1024 * 1024,
             'bounded actual software event journal required')
    lines = events.splitlines()
    _require(len(lines) <= 800000, 'software journal event ceiling exceeded')
    starts, stops, seen, active = [], [], set(), None
    failures = {key: [] for key in ('failure', 'error', 'skip', 'expected_failure', 'unexpected_success')}
    for line in lines:
        event = _json_object(line)
        _require(set(event) == {'event', 'test_id'} and _text(event['test_id']), 'exact software event fields required')
        kind, test_id = event['event'], event['test_id']
        if kind == 'start':
            _require(active is None and test_id not in seen, 'duplicate or overlapping software test start')
            starts.append(test_id)
            seen.add(test_id)
            active = test_id
        elif kind == 'stop':
            _require(active == test_id, 'software stop does not match active test')
            stops.append(test_id)
            active = None
        else:
            _require(isinstance(kind, str) and kind in failures and active is not None,
                     'unsupported or orphan software event')
            # Failing subtests have their own IDs; compare those exact IDs with
            # the result's failure lists rather than treating them as new starts.
            failures[kind].append(test_id)
    _require(active is None and starts == stops and len(starts) == goal.software_tests
             and sorted(starts) == sorted(software['executed_test_ids'])
             and software_inventory_digest(starts) == goal.software_test_inventory_sha256,
             'actual software start/stop inventory is incomplete or different')
    for kind, count, ids in (('failure', 'failures', 'failed_test_ids'), ('error', 'errors', 'error_test_ids'),
                             ('skip', 'skipped', 'skipped_test_ids'),
                             ('expected_failure', 'expected_failures', 'expected_failure_test_ids'),
                             ('unexpected_success', 'unexpected_successes', 'unexpected_success_test_ids')):
        _require(type(software.get(count)) is int and software[count] == len(failures[kind])
                 and isinstance(software.get(ids), list)
                 and canonical(sorted(failures[kind])) == canonical(software[ids]),
                 'actual software outcome events contradict report counts/IDs')
    live = _measurement_object(members, 'live-report.json')
    _require(set(live) == {'fixture_frame_source_anchor', 'tested_source_map_sha256', 'kernel', 'context'}
             and live.get('fixture_frame_source_anchor') == goal.source_commit
             and live.get('tested_source_map_sha256') == goal.source_map_sha256,
             'raw native source anchor/map differs')
    for role in ('kernel', 'context'):
        original, normalized = live.get(role), report[role]
        _require(isinstance(original, dict), 'complete raw native role required')
        mandatory = {'schema', 'status', 'tests', 'passed', 'cases', 'permissions_modified',
                     'production_service_modified', 'qualification', 'promotion_authority'}
        mandatory.update({'private_state_accessed', 'host_uid', 'systemd_version'} if role == 'kernel' else
                         {'private_context_used', 'actual_native_model_review_performed', 'source_commit'})
        _require(mandatory.issubset(original), 'mandatory raw native ' + role + ' observations missing')
        if role == 'kernel':
            _require(type(original['host_uid']) is int and original['host_uid'] == 0
                     and _text(original['systemd_version']), 'actual kernel host identity required')
        _require((original.get('source_commit') == goal.source_commit if role == 'context'
                  else 'source_commit' not in original or original['source_commit'] == goal.source_commit)
                 and ('source_map_sha256' not in original or original['source_map_sha256'] == goal.source_map_sha256),
                 'raw native role source identity differs')
        for key, value in original.items():
            if key != 'cases':
                _require(key in normalized and canonical(value) == canonical(normalized[key]),
                         'raw native ' + role + ' observation contradicts normalized report: ' + key)
        rows = original.get('cases')
        _require(isinstance(rows, list) and len(rows) <= 1000
                 and all(isinstance(row, dict) for row in rows), 'bounded raw native cases required')
        projected = [{key: row[key] for key in ('name', 'passed', 'error_class', 'error') if key in row} for row in rows]
        _require(canonical(projected) == canonical(normalized['cases']),
                 'raw native ' + role + ' case membership/outcomes contradict normalized report')


def _publication(goal, policy, reports, refs):
    publication = reports['publication']
    expected_fields = {'schema', 'repository', 'branch', 'branch_head', 'source_commit', 'source_map_sha256',
                       'status', 'readback_complete', 'tested_manifest_ref', 'published_manifest_ref',
                       'qualification', 'promotion_authority'}
    _require(set(publication) == expected_fields and publication['schema'] == 'merlin-build-publication-observation/2',
             'exact publication observation v2 required')
    _require(publication['repository'] == policy.source_repository
             and publication['branch'] == policy.publication_branch
             and publication['branch_head'] == policy.publication_head
             and publication['source_commit'] == goal.source_commit
             and publication['source_map_sha256'] == goal.source_map_sha256
             and publication['status'] == 'observed' and publication['readback_complete'] is True
             and publication['tested_manifest_ref'] == refs['tested_manifest']
             and publication['published_manifest_ref'] == refs['published_manifest'],
             'publication observation/ref binding differs')
    _no_authority(publication)
    tested, published = reports['tested_manifest'], reports['published_manifest']
    _require(tested.get('schema') == 'merlin-egm-source/2'
             and tested.get('source_kind') == 'exact_selected_candidate_shard', 'exact native selected manifest required')
    _require(published.get('schema') == 'merlin-published-source/1'
             and published.get('repository') == policy.source_repository
             and published.get('selection_scope') == 'selected_files_only', 'explicit observed selected manifest required')
    _no_authority(tested)
    _no_authority(published)
    result = {**publication, 'tested_manifest': tested, 'published_manifest': published}
    checked_publication_relation(goal, result)
    return result


def _native_reports(goal, policy, report):
    _require(report.get('schema') == 'merlin-egm-oci-validation/2'
             and report.get('source_kind') == 'exact_selected_candidate_shard'
             and report.get('source_commit') == goal.source_commit
             and report.get('source_map_sha256') == goal.source_map_sha256
             and type(report.get('run_id')) is int and report['run_id'] == policy.run_id
             and type(report.get('run_attempt')) is int and report['run_attempt'] == policy.run_attempt
             and report.get('workflow_commit') == policy.workflow_commit and report.get('runner') == policy.runner
             and report.get('fixture_frame_source_anchor') == goal.source_commit,
             'native report source/run/attempt/workflow identity differs')
    _no_authority(report)
    for key in ('actual_native_model_review_performed', 'private_context_used', 'production_service_modified',
                'permissions_modified', 'avrea_used'):
        _require(report.get(key) is False, 'native report exceeds admitted synthetic scope')
    before, after = report.get('service_before'), report.get('service_after')
    _require(isinstance(before, dict) and set(before) == {'ActiveState', 'SubState', 'MainPID', 'UnitFileState'}
             and all(_text(value) for value in before.values()) and before == after
             and before['ActiveState'] == 'active' and before['SubState'] == 'running'
             and re.fullmatch('[1-9][0-9]*', before['MainPID']) is not None
             and report.get('service_unchanged') is True, 'service observation equality not established')
    values = {}
    for role, schema in (('software', 'merlin-software-inventory/1'),
                         ('kernel', 'merlin-live-cgroup-drill/1'), ('context', 'merlin-live-review-context/1')):
        value = report.get('tests' if role == 'software' else role)
        _require(isinstance(value, dict) and value.get('schema') == schema
                 and value.get('source_commit') == goal.source_commit
                 and value.get('source_map_sha256') == goal.source_map_sha256
                 and type(value.get('run_id')) is int and value['run_id'] == policy.run_id,
                 role + ' source/run/schema differs')
        _no_authority(value)
        values[role] = value
    software = values['software']
    executed = software.get('executed_test_ids')
    collection = software.get('collection_ids')
    _require(isinstance(executed, list) and len(executed) == goal.software_tests
             and software_inventory_digest(executed) == goal.software_test_inventory_sha256
             and software.get('test_inventory_sha256') == goal.software_test_inventory_sha256
             and isinstance(collection, list)
             and software_inventory_digest(collection) == goal.software_test_inventory_sha256
             and sorted(collection) == sorted(executed)
             and software.get('collection_sha256') == goal.software_test_inventory_sha256
             and type(software.get('collected_tests')) is int and software['collected_tests'] == goal.software_tests
             and type(software.get('tests')) is int and software['tests'] == goal.software_tests
             and software.get('executed') is True and software.get('source_unchanged') is True,
             'complete actual executed software inventory differs')
    for count, ids in (('expected_failures', 'expected_failure_test_ids'),
                       ('unexpected_successes', 'unexpected_success_test_ids')):
        _require(type(software.get(count)) is int and software[count] == 0 and software.get(ids) == [],
                 'expected failure/unexpected success cannot count as acceptance')
    for role, required, private_key in (('kernel', KERNEL_CASES, 'private_state_accessed'),
                                        ('context', CONTEXT_CASES, 'private_context_used')):
        value = values[role]
        _require(type(value.get('tests')) is int and value['tests'] == len(required)
                 and type(value.get('passed')) is int and 0 <= value['passed'] <= len(required)
                 and value.get('required_case_names') == sorted(required)
                 and value.get('service_unchanged') is True and value.get(private_key) is False
                 and value.get('production_service_modified') is False and value.get('permissions_modified') is False
                 and value.get('source_identity_exact') is True and value.get('scope_exact') is True,
                 role + ' scope/count/inventory declaration differs')
        _require(value.get('source_identity_origin') == ('fixture_declared_and_host_checked' if role == 'context'
                                                       else 'host_bound_verified_source'),
                 'native source-binding origin differs')
        _require(role != 'context' or value.get('actual_native_model_review_performed') is False,
                 'context fixture cannot claim actual native model review')
        rows = value.get('cases')
        _require(isinstance(rows, list) and len(rows) <= 1000
                 and all(isinstance(row, dict) and _text(row.get('name')) and type(row.get('passed')) is bool for row in rows),
                 'bounded named Boolean cases required')
        names = [row['name'] for row in rows]
        exact = len(names) == len(required) and len(set(names)) == len(names) and set(names) == set(required)
        failed = sorted(row['name'] for row in rows if row['passed'] is False)
        _require(value.get('case_inventory_exact') is exact and value.get('failed_case_ids') == failed
                 and value['passed'] == sum(row['passed'] is True for row in rows), 'native case assertions contradict measurements')
        accepted = exact and not failed and value.get('status') == 'succeeded'
        _require(value.get('accepted') is accepted, 'native accepted flag contradicts cases')
    complete = (software.get('passed') is True and software.get('status') == 'succeeded'
                and all(values[role].get('accepted') is True for role in ('kernel', 'context')))
    _require(report.get('status') == ('succeeded' if complete else 'failed'), 'top report status contradicts measured outcomes')
    return values


def _record_ref(project_id, prefix, body):
    checksum = digest(body)
    return ArtifactRef(project_id, prefix + '/' + checksum + '.json', 1, checksum).to_dict()


def _persist(registry, ref, body):
    raw = canonical(body).encode('utf-8')
    history = registry.artifact_history(ref['project_id'], ref['logical_path'])
    _require(not history or len(history) == 1, 'immutable admission/decision has multiple versions')
    if not history:
        registry.put_artifact(ref['project_id'], ref['logical_path'], raw, 'application/json')
    _require(registry.artifact_ref(ref['project_id'], ref['logical_path'], version=1) == ref
             and registry.read_artifact_ref(ref, max_bytes=_MAX_JSON)['content'] == raw,
             'immutable admission/decision bytes differ')


def admit_oci_build(registry: MerlinRegistry, *, project_id: str, goal: BuildGoalV3,
                    policy: OCIAdmissionPolicy, references: Mapping, authenticate: Callable,
                    attempt: int = 1, previous_failure_sha256: str | None = None,
                    expected_decision_ref: Mapping | None = None):
    """Authenticate, check, record and replay one exact complete OCI observation.

    ``authenticate(role, detached_ref, byte_sha256)`` must return literal True.
    The host supplies its own trust implementation and frozen goal/policy. No
    credentials, permissive default, fetcher or global attempt ledger is created.
    Malformed/binding-inconsistent evidence fails before any record is written;
    well-formed measured case failures produce the bounded v3 stopping decision.
    All inputs are existing same-project ArtifactRefs. Generated records are
    canonical and content-addressed; original provider bytes remain referenced.
    """
    _require(isinstance(registry, MerlinRegistry) and isinstance(goal, BuildGoalV3)
             and isinstance(policy, OCIAdmissionPolicy) and isinstance(references, Mapping)
             and set(references) == EVIDENCE_ROLES and callable(authenticate),
             'canonical registry, explicit v3 goal/policy and exact authenticated references required')
    goal, policy = deepcopy(goal), deepcopy(policy)
    expected = (ArtifactRef.from_mapping(deepcopy(expected_decision_ref)).to_dict()
                if expected_decision_ref is not None else None)
    goal.validate()
    policy.validate()
    _require(set(goal.required_kernel_cases) == set(KERNEL_CASES)
             and set(goal.required_context_cases) == set(CONTEXT_CASES), 'this adapter requires the fixed eight kernel/six context checks')
    refs = {role: ArtifactRef.from_mapping(deepcopy(references[role])).to_dict() for role in sorted(EVIDENCE_ROLES)}
    _require(all(ref['project_id'] == project_id for ref in refs.values()), 'cross-project evidence rejected')
    raw = {}
    for role, ref in refs.items():
        limit = _MAX_ARCHIVE if role == 'archive' else 64 * 1024 if role in ('controller', 'workflow') else _MAX_JSON
        raw[role] = registry.read_artifact_ref(ref, max_bytes=limit)['content']
        if authenticate(role, deepcopy(ref), ref['sha256']) is not True:
            raise PermissionError('exact ' + role + ' evidence is not authenticated by the host')
    reports = {role: _json_object(body, canonical_required=role in ('publication', 'published_manifest'))
               for role, body in raw.items() if role not in ('archive', 'controller', 'workflow')}
    publication = _publication(goal, policy, reports, refs)
    _check_provider(policy, reports, raw)
    members = _check_archive(goal, reports, raw)
    native = _native_reports(goal, policy, reports['report'])
    _check_measurements(goal, reports['report'], members)
    _require(reports['run']['conclusion'] == ('success' if reports['report']['status'] == 'succeeded' else 'failure'),
             'provider conclusion contradicts complete native report')
    decision = decide_build_v3(goal, publication=publication, **native, attempt=attempt,
                               previous_failure_sha256=previous_failure_sha256)
    # Re-read exact bytes after every callback has run. Callback arguments are
    # detached; mutations of registry bytes or caller-owned references cannot
    # silently alter the authenticated snapshot used for the decision.
    for role, ref in refs.items():
        _require(registry.read_artifact_ref(ref, max_bytes=_MAX_ARCHIVE)['content'] == raw[role],
                 'evidence mutated during host authentication')
    admission = {'schema': 'merlin-build-evidence-admission/1', 'goal': asdict(goal),
                 'policy': asdict(policy), 'evidence_refs': refs,
                 'publication_relation': decision['publication_relation'],
                 'qualification': False, 'promotion_authority': False,
                 'live_service_wiring_provisioned': False}
    admission_ref = _record_ref(project_id, 'build-evidence-admissions', admission)
    decision.update(admission_ref=admission_ref, evidence_refs=refs,
                    native_execution={'repository': policy.workflow_repository, 'run_id': policy.run_id,
                        'run_attempt': policy.run_attempt, 'workflow_commit': policy.workflow_commit,
                        'workflow_git_blob': policy.workflow_git_blob, 'workflow_sha256': policy.workflow_sha256,
                        'controller_git_blob': policy.controller_git_blob, 'controller_sha256': policy.controller_sha256,
                        'artifact_id': policy.artifact_id, 'artifact_sha256': policy.artifact_sha256},
                    actual_native_model_review_performed=False, live_service_wiring_provisioned=False)
    decision_ref = _record_ref(project_id, 'build-loop-decisions', decision)
    if expected is not None:
        _require(expected == decision_ref, 'recomputed decision differs from exact replay reference')
    _persist(registry, admission_ref, admission)
    _persist(registry, decision_ref, decision)
    return {**decision, 'decision_ref': decision_ref}


def replay_oci_build_decision(registry: MerlinRegistry, *, project_id: str, goal: BuildGoalV3,
                              policy: OCIAdmissionPolicy, decision_ref: Mapping,
                              authenticate: Callable, attempt: int = 1,
                              previous_failure_sha256: str | None = None):
    """Reauthenticate original evidence under host-supplied criteria after restart.

    Stored goals or policies cannot lower current host requirements. Recomputed
    identity must match before any persistence; replay is not a new native run.
    """
    ref = ArtifactRef.from_mapping(deepcopy(decision_ref)).to_dict()
    _require(ref['project_id'] == project_id, 'cross-project decision replay rejected')
    body = _json_object(registry.read_artifact_ref(ref, max_bytes=_MAX_JSON)['content'], canonical_required=True)
    _require(body.get('schema') == 'merlin-build-loop-decision/3', 'exact v3 decision required')
    return admit_oci_build(registry, project_id=project_id, goal=goal, policy=policy,
                           references=body.get('evidence_refs'), authenticate=authenticate,
                           attempt=attempt, previous_failure_sha256=previous_failure_sha256,
                           expected_decision_ref=ref)
