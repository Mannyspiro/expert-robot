"""Synthetic custody fixtures only; no real native evidence is admitted here."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from merlin.branch_research import canonical, digest
from merlin.build_admission import (CONTEXT_CASES, KERNEL_CASES, OCIAdmissionPolicy,
                                    admit_oci_build, replay_oci_build_decision)
from merlin.build_loop import (BuildGoal, BuildGoalV3, decide_build, decide_build_v3,
                               software_inventory_digest)
from merlin.project_registry import MerlinRegistry


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def original_json(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def zipped(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(files.items()):
            item = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            item.external_attr = 0o100644 << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(item, raw)
    return output.getvalue()


class SyntheticObservation:
    """Deliberately non-production IDs/bytes and a fixture-only exact allowlist."""

    def __init__(self, root):
        self.registry = MerlinRegistry(root)
        self.registry.register_project('fixture', 'Synthetic build evidence custody')
        self.files = {'python/fixture.py': b'# synthetic source; never executed\n',
                      'tests/test_fixture.py': b'# synthetic selection; never executed\n'}
        self.workflow = b'# synthetic workflow bytes; not executable validation\n'
        self.controller = b'# synthetic controller bytes; not executed\n'
        self.ids = ['fixture.Tests.test_%d' % value for value in range(3)]
        files = {name: sha(raw) for name, raw in self.files.items()}
        self.goal = BuildGoalV3('a' * 40, digest(files), 3, len(KERNEL_CASES),
                               software_test_inventory_sha256=software_inventory_digest(self.ids),
                               required_kernel_cases=KERNEL_CASES, source_files=2,
                               required_context_cases=CONTEXT_CASES)
        self.binding = {'source_commit': self.goal.source_commit, 'source_map_sha256': self.goal.source_map_sha256,
                        'qualification': False, 'promotion_authority': False}
        tested = dict(self.binding, schema='merlin-egm-source/2', source_kind='exact_selected_candidate_shard',
                      files=files, git_blobs={name: git(raw) for name, raw in self.files.items()})
        published = dict(tested, schema='merlin-published-source/1', source_commit='b' * 40,
                         repository='fixture/source', selection_scope='selected_files_only')
        software = dict(self.binding, schema='merlin-software-inventory/1', run_id=123,
                        tests=3, collected_tests=3, collection_ids=list(self.ids),
                        collection_sha256=self.goal.software_test_inventory_sha256,
                        executed_test_ids=list(self.ids), test_inventory_sha256=self.goal.software_test_inventory_sha256,
                        executed=True, source_unchanged=True, passed=True, status='succeeded',
                        failures=0, errors=0, skipped=0, expected_failures=0, unexpected_successes=0,
                        failed_test_ids=[], error_test_ids=[], skipped_test_ids=[],
                        expected_failure_test_ids=[], unexpected_success_test_ids=[])
        def cases(names, schema, private):
            value = dict(self.binding, schema=schema, run_id=123, status='succeeded', tests=len(names), passed=len(names),
                         cases=[{'name': name, 'passed': True} for name in names], required_case_names=sorted(names),
                         service_unchanged=True, source_identity_exact=True, scope_exact=True,
                         case_inventory_exact=True, accepted=True, failed_case_ids=[],
                         production_service_modified=False, permissions_modified=False)
            value[private] = False
            return value
        kernel = cases(KERNEL_CASES, 'merlin-live-cgroup-drill/1', 'private_state_accessed')
        kernel.update(host_uid=0, systemd_version='systemd synthetic fixture')
        context = cases(CONTEXT_CASES, 'merlin-live-review-context/1', 'private_context_used')
        context['actual_native_model_review_performed'] = False
        kernel['source_identity_origin'] = 'host_bound_verified_source'
        context['source_identity_origin'] = 'fixture_declared_and_host_checked'
        service = {'ActiveState': 'active', 'SubState': 'running', 'MainPID': '4321', 'UnitFileState': 'enabled'}
        report = dict(self.binding, schema='merlin-egm-oci-validation/2', source_kind='exact_selected_candidate_shard',
                      run_id=123, run_attempt=2, workflow_commit='c' * 40, runner='fixture-runner', status='succeeded',
                      fixture_frame_source_anchor=self.goal.source_commit, tests=software, kernel=kernel, context=context,
                      actual_native_model_review_performed=False, private_context_used=False, permissions_modified=False,
                      production_service_modified=False, avrea_used=False, service_before=service,
                      service_after=dict(service), service_unchanged=True)
        self.documents = {
            'tested_manifest': tested, 'published_manifest': published, 'report': report,
            'publication': dict(self.binding, schema='merlin-build-publication-observation/2', repository='fixture/source',
                                branch='fixture-source-branch', branch_head='b' * 40, status='observed', readback_complete=True),
            'controller_identity': dict(git_blob=git(self.controller), sha256=sha(self.controller), bytes=len(self.controller),
                                        workflow_commit='c' * 40),
            'run': dict(id=123, run_attempt=2, head_sha='c' * 40, path='.github/workflows/fixture.yml',
                        head_branch='fixture-validation', status='completed', conclusion='success',
                        repository={'id': 999, 'full_name': 'fixture/validation'}),
        }

    def store(self):
        raw = {name: (canonical(body).encode() if name == 'published_manifest' else original_json(body))
               for name, body in self.documents.items() if name != 'publication'}
        raw.update(controller=self.controller, workflow=self.workflow)
        package = zipped({**self.files, 'manifest.json': raw['tested_manifest']})
        self.documents['report']['source_package_sha256'] = sha(package)
        raw['report'] = original_json(self.documents['report'])
        report = self.documents['report']
        derived = {'run_id', 'service_unchanged', 'required_case_names', 'case_inventory_exact', 'failed_case_ids',
                   'source_identity_origin', 'source_identity_exact', 'scope_exact', 'accepted', 'source_map_sha256'}
        live = {'fixture_frame_source_anchor': self.goal.source_commit,
                'tested_source_map_sha256': self.goal.source_map_sha256}
        for role in ('kernel', 'context'):
            live[role] = {key: value for key, value in report[role].items() if key not in derived} if role in report else {}
        live['kernel'].pop('source_commit', None)
        events = b''.join((json.dumps({'event': kind, 'test_id': test_id}, sort_keys=True) + '\n').encode()
                          for test_id in self.ids for kind in ('start', 'stop'))
        self.members = {'tested-source.zip': package, 'source-manifest.json': raw['tested_manifest'],
                        'report.json': raw['report'], 'controller.txt': self.controller,
                        'controller-identity.json': raw['controller_identity'],
                        'software-report.json': original_json(report['tests']),
                        'software-report.events.txt': events, 'live-report.json': original_json(live)}
        raw['archive'] = zipped(self.members)
        self.policy = OCIAdmissionPolicy(
            source_repository='fixture/source', publication_branch='fixture-source-branch', publication_head='b' * 40,
            workflow_repository='fixture/validation', workflow_branch='fixture-validation',
            workflow_path='.github/workflows/fixture.yml', workflow_commit='c' * 40,
            workflow_git_blob=git(self.workflow), workflow_sha256=sha(self.workflow),
            controller_git_blob=git(self.controller), controller_sha256=sha(self.controller),
            run_id=123, run_attempt=2, runner='fixture-runner', artifact_id=456,
            artifact_name='merlin-egm-123-2', artifact_sha256=sha(raw['archive']), artifact_bytes=len(raw['archive']))
        metadata = {'artifacts': [{'id': 456, 'name': self.policy.artifact_name,
                                   'size_in_bytes': len(raw['archive']), 'digest': 'sha256:' + sha(raw['archive']),
                                   'expired': False, 'workflow_run': {'id': 123, 'repository_id': 999,
                                       'head_repository_id': 999, 'head_sha': 'c' * 40, 'head_branch': 'fixture-validation'}}]}
        self.documents['artifact_metadata'] = metadata
        raw['artifact_metadata'] = original_json(metadata)
        self.refs = {}
        for role, body in raw.items():
            self.put(role, body)
        self.documents['publication'].setdefault('tested_manifest_ref', self.refs['tested_manifest'])
        self.documents['publication'].setdefault('published_manifest_ref', self.refs['published_manifest'])
        self.put('publication', canonical(self.documents['publication']).encode())
        self.allowlist = {(role, canonical(ref), ref['sha256']) for role, ref in self.refs.items()}
        return self

    def put(self, role, body):
        path = 'synthetic-inputs/' + role
        self.registry.put_artifact('fixture', path, body)
        self.refs[role] = self.registry.artifact_ref('fixture', path)

    def authenticate(self, role, ref, checksum):
        return (role, canonical(ref), checksum) in self.allowlist

    def admit(self, **changes):
        inputs = dict(project_id='fixture', goal=self.goal, policy=self.policy,
                      references=self.refs, authenticate=self.authenticate)
        inputs.update(changes)
        return admit_oci_build(self.registry, **inputs)

    def replace_evidence(self, role, body):
        self.put(role, body)
        self.allowlist = {(name, canonical(ref), ref['sha256']) for name, ref in self.refs.items()}

    def repin_archive(self, members):
        """Consistent synthetic custody pins ensure tests reach measurement checks."""
        raw = zipped(members)
        self.policy = replace(self.policy, artifact_sha256=sha(raw), artifact_bytes=len(raw))
        metadata = deepcopy(self.documents['artifact_metadata'])
        metadata['artifacts'][0].update(digest='sha256:' + sha(raw), size_in_bytes=len(raw))
        self.replace_evidence('archive', raw)
        self.replace_evidence('artifact_metadata', original_json(metadata))

    def failed_case(self, role, *, index=0, new_name=None):
        value = self.documents['report'][role]
        if new_name is None:
            value['cases'][index]['passed'] = False
        else:
            value['cases'][index]['name'] = new_name
        names = [row['name'] for row in value['cases']]
        required = KERNEL_CASES if role == 'kernel' else CONTEXT_CASES
        value.update(passed=sum(row['passed'] for row in value['cases']),
                     failed_case_ids=sorted(row['name'] for row in value['cases'] if not row['passed']),
                     case_inventory_exact=len(set(names)) == len(names) and set(names) == set(required),
                     accepted=False, status='failed')
        self.documents['report']['status'] = 'failed'
        self.documents['run']['conclusion'] = 'failure'


class BuildAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.fixture = SyntheticObservation(self.root / 'registry')

    def assert_rejected(self, fixture=None, **changes):
        fixture = fixture or self.fixture
        with self.assertRaises((ValueError, PermissionError, RuntimeError)):
            fixture.admit(**changes)

    def test_canonical_admission_and_restart_replay_preserve_exact_head_and_refs(self):
        f = self.fixture.store()
        first = f.admit()
        self.assertEqual(first['schema'], 'merlin-build-loop-decision/3')
        self.assertEqual(first['state'], 'ready_for_review')
        self.assertEqual(first['publication_relation']['tested_source_commit'], 'a' * 40)
        self.assertEqual(first['publication_relation']['observed_publication_head'], 'b' * 40)
        self.assertEqual(first['publication_relation']['relationship'], 'identical_selected_files')
        self.assertFalse(first['publication_relation']['whole_commit_equivalence'])
        self.assertFalse(first['publication_relation']['ancestry_verified'])
        self.assertEqual(first['native_execution']['run_attempt'], 2)
        self.assertEqual(first['acceptance']['required_context_cases'], sorted(CONTEXT_CASES))
        for key in ('qualification', 'promotion_authority', 'merge_authorized', 'deployment_authorized',
                    'automatic_retry', 'actual_native_model_review_performed', 'live_service_wiring_provisioned'):
            self.assertIs(first[key], False)
        self.assertEqual(f.admit(), first)
        restarted = MerlinRegistry(f.registry.root)
        replay = replay_oci_build_decision(restarted, project_id='fixture', goal=f.goal, policy=f.policy,
                                           decision_ref=first['decision_ref'], authenticate=f.authenticate)
        self.assertEqual(replay, first)
        for key in ('admission_ref', 'decision_ref'):
            ref = first[key]
            self.assertEqual(len(restarted.artifact_history('fixture', ref['logical_path'])), 1)
            raw = restarted.read_artifact_ref(ref)['content']
            self.assertEqual(raw, canonical(json.loads(raw)).encode())

    def test_v2_still_rejects_different_head_while_v3_checks_selected_source_relation(self):
        f = self.fixture.store()
        publication = dict(f.documents['publication'], tested_manifest=f.documents['tested_manifest'],
                           published_manifest=f.documents['published_manifest'])
        reports = f.documents['report']
        old_goal = BuildGoal(f.goal.source_commit, f.goal.source_map_sha256, 3, len(KERNEL_CASES),
                            software_test_inventory_sha256=f.goal.software_test_inventory_sha256,
                            required_kernel_cases=KERNEL_CASES)
        v2 = decide_build(old_goal, publication=publication, software=reports['tests'], kernel=reports['kernel'], attempt=1)
        v3 = decide_build_v3(f.goal, publication=publication, software=reports['tests'], kernel=reports['kernel'],
                             context=reports['context'], attempt=1)
        self.assertEqual(v2['schema'], 'merlin-build-loop-decision/2')
        self.assertIn('publication:unconfirmed', v2['reasons'])
        self.assertEqual(v3['state'], 'ready_for_review')
        self.assertEqual(publication['branch_head'], 'b' * 40)

    def test_published_manifest_different_membership_same_count_is_rejected(self):
        manifest = self.fixture.documents['published_manifest']
        for key in ('files', 'git_blobs'):
            manifest[key] = dict(manifest[key])
            manifest[key]['python/unrelated.py'] = manifest[key].pop('python/fixture.py')
        manifest['source_map_sha256'] = digest(manifest['files'])
        self.fixture.store()
        self.assert_rejected()

    def test_missing_extra_or_changed_selected_source_cannot_be_hidden_by_map_label(self):
        for change in ('missing', 'extra', 'hash'):
            with self.subTest(change=change):
                f = SyntheticObservation(self.root / change)
                m = deepcopy(f.documents['published_manifest'])
                f.documents['published_manifest'] = m
                if change == 'missing':
                    m['files'].pop('python/fixture.py'); m['git_blobs'].pop('python/fixture.py')
                elif change == 'extra':
                    m['files']['python/extra.py'] = 'd' * 64; m['git_blobs']['python/extra.py'] = 'e' * 40
                else:
                    m['files']['python/fixture.py'] = 'd' * 64
                f.store()
                self.assert_rejected(f)

    def test_git_blob_only_disagreement_is_rejected(self):
        f = self.fixture
        f.documents['published_manifest'] = deepcopy(f.documents['published_manifest'])
        f.documents['published_manifest']['git_blobs']['python/fixture.py'] = 'd' * 40
        f.store()
        self.assert_rejected()

    def test_observed_head_must_match_both_host_policy_and_manifest(self):
        for target in ('publication', 'published_manifest'):
            with self.subTest(target=target):
                f = SyntheticObservation(self.root / target)
                f.documents[target]['branch_head' if target == 'publication' else 'source_commit'] = 'd' * 40
                f.store()
                self.assert_rejected(f)

    def test_source_commit_and_map_are_bound_at_every_report_level(self):
        for field, wrong in (('source_commit', 'd' * 40), ('source_map_sha256', 'e' * 64)):
            for role in ('publication', 'tested_manifest', 'published_manifest', 'report', 'tests', 'kernel', 'context'):
                with self.subTest(field=field, role=role):
                    f = SyntheticObservation(self.root / (field + role))
                    target = f.documents['report'][role] if role in ('tests', 'kernel', 'context') else f.documents[role]
                    target[field] = wrong
                    f.store()
                    self.assert_rejected(f)

    def test_actual_source_zip_bytes_must_match_both_hash_algorithms(self):
        self.fixture.files['python/fixture.py'] = b'# modified source after manifest\n'
        self.fixture.store()
        self.assert_rejected()

    def test_run_attempt_not_just_run_id_is_pinned(self):
        for role in ('report', 'run'):
            for wrong in (1, True, 2.0):
                with self.subTest(role=role, wrong=wrong):
                    f = SyntheticObservation(self.root / ('%s-%s-%s' % (role, type(wrong).__name__, wrong)))
                    f.documents[role]['run_attempt'] = wrong
                    f.store()
                    self.assert_rejected(f)

    def test_workflow_commit_path_repository_and_runner_cannot_drift(self):
        changes = [('run', 'head_sha', 'd' * 40), ('run', 'path', '.github/workflows/other.yml'),
                   ('run', 'repository', {'id': 999, 'full_name': 'fixture/other'}),
                   ('report', 'runner', 'unrelated-runner'), ('controller_identity', 'workflow_commit', 'd' * 40)]
        for index, (role, key, value) in enumerate(changes):
            with self.subTest(role=role, key=key):
                f = SyntheticObservation(self.root / str(index))
                f.documents[role][key] = value
                f.store()
                self.assert_rejected(f)

    def test_controller_and_workflow_require_actual_bytes_and_git_identity(self):
        f = self.fixture.store()
        for field, value in (('controller_sha256', 'd' * 64), ('controller_git_blob', 'e' * 40),
                             ('workflow_sha256', 'f' * 64), ('workflow_git_blob', 'd' * 40)):
            with self.subTest(field=field):
                self.assert_rejected(policy=replace(f.policy, **{field: value}))

    def test_controller_receipt_hash_size_and_blob_are_checked(self):
        for key, wrong in (('sha256', 'd' * 64), ('git_blob', 'e' * 40), ('bytes', True), ('bytes', 1)):
            with self.subTest(key=key, wrong=wrong):
                f = SyntheticObservation(self.root / (key + str(wrong)))
                f.documents['controller_identity'][key] = wrong
                f.store()
                self.assert_rejected(f)

    def test_artifact_provider_metadata_binds_run_attempt_name_bytes_and_digest(self):
        changes = [('name', 'merlin-egm-123-1'), ('digest', 'sha256:' + 'd' * 64), ('size_in_bytes', True),
                   ('expired', True), ('workflow_run', {'id': 124})]
        for index, (key, wrong) in enumerate(changes):
            with self.subTest(key=key):
                f = SyntheticObservation(self.root / str(index)).store()
                metadata = deepcopy(f.documents['artifact_metadata'])
                metadata['artifacts'][0][key] = wrong
                f.replace_evidence('artifact_metadata', original_json(metadata))
                self.assert_rejected(f)

    def test_detached_authentic_report_must_still_be_exact_archived_member(self):
        f = self.fixture.store()
        report = deepcopy(f.documents['report'])
        report['unrelated_note'] = 'different original bytes'
        f.replace_evidence('report', original_json(report))
        self.assert_rejected()

    def test_selected_artifact_hash_cannot_be_replaced_by_another_valid_zip(self):
        f = self.fixture.store()
        f.replace_evidence('archive', zipped({'unrelated.txt': b'unrelated'}))
        self.assert_rejected()

    def test_authenticated_archive_still_rejects_unsafe_or_excessive_members(self):
        for change in ('traversal', 'symlink', 'too_many'):
            with self.subTest(change=change):
                f = SyntheticObservation(self.root / change).store()
                old = f.registry.read_artifact_ref(f.refs['archive'])['content']
                with zipfile.ZipFile(io.BytesIO(old)) as archive:
                    files = {name: archive.read(name) for name in archive.namelist()}
                output = io.BytesIO()
                with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
                    for name, raw in files.items():
                        archive.writestr(name, raw)
                    if change == 'traversal': archive.writestr('../escape', b'blocked')
                    elif change == 'symlink':
                        item = zipfile.ZipInfo('link')
                        item.external_attr = 0o120777 << 16
                        archive.writestr(item, b'report.json')
                    else:
                        for index in range(41): archive.writestr('extra-%d' % index, b'')
                raw = output.getvalue()
                f.policy = replace(f.policy, artifact_sha256=sha(raw), artifact_bytes=len(raw))
                metadata = deepcopy(f.documents['artifact_metadata'])
                metadata['artifacts'][0].update(digest='sha256:' + sha(raw), size_in_bytes=len(raw))
                f.replace_evidence('archive', raw)
                f.replace_evidence('artifact_metadata', original_json(metadata))
                self.assert_rejected(f)

    def test_actual_executed_software_ids_not_only_claimed_digest_are_checked(self):
        for change in ('different', 'duplicate', 'collection', 'boolean_count', 'not_executed', 'source_changed'):
            with self.subTest(change=change):
                f = SyntheticObservation(self.root / change)
                report = f.documents['report']['tests']
                if change == 'different': report['executed_test_ids'][-1] = 'fixture.Tests.unrelated'
                elif change == 'duplicate': report['executed_test_ids'][-1] = report['executed_test_ids'][0]
                elif change == 'collection': report['collection_ids'][-1] = 'fixture.Tests.unrelated'
                elif change == 'boolean_count': report['tests'] = True
                elif change == 'not_executed': report['executed'] = False
                else: report['source_unchanged'] = False
                f.store()
                self.assert_rejected(f)

    def test_missing_retained_measurements_cannot_be_replaced_by_normalized_claims(self):
        for name in ('software-report.json', 'software-report.events.txt', 'live-report.json'):
            with self.subTest(name=name):
                f = SyntheticObservation(self.root / name).store()
                members = dict(f.members)
                members.pop(name)
                f.repin_archive(members)
                self.assert_rejected(f)

    def test_contradictory_retained_software_report_is_rejected_with_consistent_artifact_pins(self):
        f = self.fixture.store()
        members = dict(f.members)
        software = json.loads(members['software-report.json'])
        software.update(passed=False, tests=0, executed_test_ids=[], status='failed')
        members['software-report.json'] = original_json(software)
        f.repin_archive(members)
        self.assert_rejected()

    def test_missing_different_duplicate_or_unfinished_software_events_are_rejected(self):
        for change in ('different', 'missing_stop', 'duplicate', 'wrong_stop', 'extra_failure'):
            with self.subTest(change=change):
                f = SyntheticObservation(self.root / change).store()
                members = dict(f.members)
                events = [json.loads(line) for line in members['software-report.events.txt'].splitlines()]
                if change == 'different':
                    events[0]['test_id'] = events[1]['test_id'] = 'fixture.Tests.unrelated'
                elif change == 'missing_stop': events.pop()
                elif change == 'duplicate': events.extend(deepcopy(events[-2:]))
                elif change == 'wrong_stop': events[1]['test_id'] = 'fixture.Tests.unrelated'
                else: events.insert(1, {'event': 'failure', 'test_id': f.ids[0]})
                members['software-report.events.txt'] = (
                    '\n'.join(json.dumps(event, sort_keys=True) for event in events) + '\n').encode()
                f.repin_archive(members)
                self.assert_rejected(f)

    def test_raw_native_case_pass_membership_and_source_must_agree_with_summary(self):
        for role in ('kernel', 'context'):
            for change in ('pass', 'membership', 'source_map', 'source_commit', 'count'):
                with self.subTest(role=role, change=change):
                    f = SyntheticObservation(self.root / (role + change)).store()
                    members = dict(f.members)
                    live = json.loads(members['live-report.json'])
                    value = live[role]
                    if change == 'pass': value['cases'][0]['passed'] = False
                    elif change == 'membership': value['cases'][0]['name'] = 'unrelated'
                    elif change == 'source_map': live['tested_source_map_sha256'] = 'd' * 64
                    elif change == 'source_commit': value['source_commit'] = 'e' * 40
                    else: value['passed'] -= 1
                    members['live-report.json'] = original_json(live)
                    f.repin_archive(members)
                    self.assert_rejected(f)

    def test_raw_native_roles_cannot_omit_required_observations(self):
        shared = ('schema', 'status', 'tests', 'passed', 'permissions_modified',
                  'production_service_modified', 'qualification', 'promotion_authority')
        for role in ('kernel', 'context'):
            specific = (('private_state_accessed', 'host_uid', 'systemd_version') if role == 'kernel' else
                        ('private_context_used', 'actual_native_model_review_performed', 'source_commit'))
            for field in shared + specific + ('all_except_cases',):
                with self.subTest(role=role, field=field):
                    f = SyntheticObservation(self.root / (role + field)).store()
                    members = dict(f.members)
                    live = json.loads(members['live-report.json'])
                    if field == 'all_except_cases':
                        live[role] = {'cases': live[role]['cases']}
                        if role == 'context': live[role]['source_commit'] = f.goal.source_commit
                    else:
                        live[role].pop(field)
                    members['live-report.json'] = original_json(live)
                    f.repin_archive(members)
                    self.assert_rejected(f)

    def test_expected_failure_or_unexpected_success_cannot_count_as_pass(self):
        for count, ids in (('expected_failures', 'expected_failure_test_ids'),
                           ('unexpected_successes', 'unexpected_success_test_ids')):
            with self.subTest(count=count):
                f = SyntheticObservation(self.root / count)
                f.documents['report']['tests'].update({count: 1, ids: [f.ids[0]]})
                f.store()
                self.assert_rejected(f)

    def test_invalid_collection_ids_fail_as_validation_errors(self):
        f = self.fixture
        f.documents['report']['tests']['collection_ids'][-1] = None
        f.store()
        with self.assertRaises(ValueError):
            f.admit()

    def test_different_eight_or_six_passing_cases_produce_rejection_decision(self):
        for role in ('kernel', 'context'):
            with self.subTest(role=role):
                f = SyntheticObservation(self.root / role)
                f.failed_case(role, new_name='unrelated_but_passing_case')
                f.store()
                decision = f.admit()
                self.assertEqual(decision['state'], 'repair_required')
                self.assertIn(role + ':case_inventory_mismatch', decision['reasons'])

    def test_failed_sixth_context_case_blocks_even_when_software_and_kernel_pass(self):
        f = self.fixture
        f.failed_case('context', index=CONTEXT_CASES.index('completed_process_checker_recovery_without_relaunch'))
        f.store()
        first = f.admit()
        self.assertEqual(first['state'], 'repair_required')
        self.assertIn('context:acceptance_failed', first['reasons'])
        repeated = f.admit(attempt=2, previous_failure_sha256=first['failure_sha256'])
        self.assertEqual(repeated['state'], 'stalled')
        self.assertEqual(first['failure_sha256'], repeated['failure_sha256'])
        self.assertFalse(repeated['automatic_retry'])

    def test_duplicate_case_or_forged_accepted_flag_cannot_pass(self):
        for change in ('duplicate', 'forged_flag'):
            with self.subTest(change=change):
                f = SyntheticObservation(self.root / change)
                if change == 'duplicate':
                    f.documents['report']['context']['cases'][0] = dict(f.documents['report']['context']['cases'][1])
                else:
                    f.documents['report']['context']['cases'][0]['passed'] = False
                f.store()
                self.assert_rejected(f)

    def test_service_equal_flag_cannot_hide_changed_pid(self):
        f = self.fixture
        f.documents['report']['service_after']['MainPID'] = '5678'
        f.store()
        self.assert_rejected()

    def test_native_review_authority_and_private_access_claims_are_rejected(self):
        for role, key in (('report', 'qualification'), ('report', 'promotion_authority'),
                          ('report', 'actual_native_model_review_performed'), ('context', 'private_context_used'),
                          ('kernel', 'permissions_modified')):
            with self.subTest(role=role, key=key):
                f = SyntheticObservation(self.root / (role + key))
                target = f.documents['report'] if role == 'report' else f.documents['report'][role]
                target[key] = True
                f.store()
                self.assert_rejected(f)

    def test_non_boolean_authentication_cannot_grant_trust(self):
        f = self.fixture.store()
        for value in (False, 1, 'yes', {'verified': True}, None):
            with self.subTest(value=value):
                self.assert_rejected(authenticate=lambda *args, result=value: result)
        self.assertEqual(f.registry.artifact_history('fixture', 'build-evidence-admissions/anything.json'), [])

    def test_callback_receives_only_detached_exact_reference_and_digest(self):
        f = self.fixture.store()
        original_refs = deepcopy(f.refs)
        calls = []
        def authenticate(role, ref, checksum):
            accepted = f.authenticate(role, ref, checksum)
            calls.append((role, deepcopy(ref), checksum))
            ref['sha256'] = 'f' * 64
            return accepted
        result = f.admit(authenticate=authenticate)
        self.assertEqual(result['state'], 'ready_for_review')
        self.assertEqual(f.refs, original_refs)
        self.assertEqual({role for role, _, _ in calls}, set(f.refs))
        self.assertTrue(all(ref == f.refs[role] and checksum == ref['sha256'] for role, ref, checksum in calls))

    def test_callback_mutating_caller_reference_cannot_change_snapshot(self):
        f = self.fixture.store()
        expected = deepcopy(f.refs)
        def authenticate(role, ref, checksum):
            accepted = f.authenticate(role, ref, checksum)
            f.refs['report']['sha256'] = 'f' * 64
            return accepted
        result = f.admit(authenticate=authenticate)
        self.assertEqual(result['evidence_refs'], expected)

    def test_callback_mutating_already_read_registry_bytes_is_detected_before_persistence(self):
        f = self.fixture.store()
        def authenticate(role, ref, checksum):
            accepted = f.authenticate(role, ref, checksum)
            if role == 'workflow':
                target = f.refs['archive']['sha256']
                (f.registry.blobs / target[:2] / target[2:]).write_bytes(b'changed during authentication')
            return accepted
        self.assert_rejected(authenticate=authenticate)

    def test_callback_cannot_replace_the_expected_replay_identity(self):
        f = self.fixture.store()
        original = f.admit()
        expected = dict(original['decision_ref'], sha256='d' * 64)
        def authenticate(role, ref, checksum):
            accepted = f.authenticate(role, ref, checksum)
            expected.update(original['decision_ref'])
            return accepted
        self.assert_rejected(authenticate=authenticate, expected_decision_ref=expected)

    def test_cross_project_and_wrong_exact_digest_references_are_rejected(self):
        f = self.fixture.store()
        for field, wrong in (('project_id', 'other'), ('sha256', 'f' * 64)):
            with self.subTest(field=field):
                refs = deepcopy(f.refs)
                refs['report'][field] = wrong
                self.assert_rejected(references=refs)

    def test_publication_must_bind_exact_manifest_references(self):
        f = self.fixture.store()
        publication = deepcopy(f.documents['publication'])
        publication['published_manifest_ref']['sha256'] = 'd' * 64
        f.replace_evidence('publication', canonical(publication).encode())
        self.assert_rejected()

    def test_original_pretty_json_is_preserved_but_duplicate_keys_and_nan_are_rejected(self):
        f = self.fixture.store()
        self.assertEqual(f.admit()['state'], 'ready_for_review')
        for raw in (b'{"id":123,"id":123}', b'{"id":NaN}'):
            f.replace_evidence('run', raw)
            self.assert_rejected()

    def test_host_publication_envelope_must_be_canonical(self):
        f = self.fixture.store()
        f.replace_evidence('publication', original_json(f.documents['publication']))
        self.assert_rejected()

    def test_replay_reauthenticates_original_evidence_and_cannot_lower_host_requirements(self):
        f = self.fixture.store()
        original = f.admit()
        kwargs = dict(project_id='fixture', goal=f.goal, policy=f.policy, decision_ref=original['decision_ref'])
        with self.assertRaises(PermissionError):
            replay_oci_build_decision(f.registry, **kwargs, authenticate=lambda *args: False)
        with self.assertRaises(ValueError):
            replay_oci_build_decision(f.registry, **dict(kwargs, policy=replace(f.policy, run_attempt=3)),
                                      authenticate=f.authenticate)
        with self.assertRaises(ValueError):
            replay_oci_build_decision(f.registry, **kwargs, authenticate=f.authenticate, attempt=2)

    def test_replay_rejects_forged_derived_decision_even_with_valid_original_evidence(self):
        f = self.fixture.store()
        original = f.admit()
        forged = {key: value for key, value in original.items() if key != 'decision_ref'}
        forged['deployment_authorized'] = True
        path = 'forged/decision.json'
        f.registry.put_artifact('fixture', path, canonical(forged).encode())
        with self.assertRaises(ValueError):
            replay_oci_build_decision(f.registry, project_id='fixture', goal=f.goal, policy=f.policy,
                                      decision_ref=f.registry.artifact_ref('fixture', path), authenticate=f.authenticate)

    def test_missing_context_role_cannot_fall_back_to_v2(self):
        f = self.fixture
        f.documents['report'].pop('context')
        f.store()
        self.assert_rejected()

    def test_admission_preserves_inputs_and_distinguishes_build_attempt_from_native_attempt(self):
        f = self.fixture.store()
        before = deepcopy((f.documents, f.refs, f.goal, f.policy))
        result = f.admit(attempt=1)
        self.assertEqual(result['attempt'], 1)
        self.assertEqual(result['native_execution']['run_attempt'], 2)
        self.assertEqual(before, (f.documents, f.refs, f.goal, f.policy))


if __name__ == '__main__':
    unittest.main()
