"""Actual worker/outbox fault injection; synthetic tasks and authority fixtures."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from merlin.branch_research import Branch
from merlin.branch_registry import RegistryBranchSession, build_branch_research_executor
from merlin.project_registry import MerlinRegistry
from merlin.event_outbox import MerlinEventOutbox, LeaseConflict
from merlin.hermes_worker import HermesWorker, HERMES_TASK_TOPIC
from merlin.hermes_stage_handlers import build_hermes_stage_handlers
from merlin.research_evidence import ResearchEvidenceRecorder
from merlin.hypothesis_ledger import HypothesisLedger
from merlin.knowledge_graph import MerlinKnowledgeGraph
from dot_ai_os.research_protocol import research_episode_demo, store_research_record, _validated_plan


class BranchWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.registry = MerlinRegistry(self.root / 'registry')
        self.registry.register_project('test', 'Synthetic worker contract')
        self.frame = research_episode_demo({})['research_plan']
        self.frame_ref = store_research_record(self.registry, 'test', self.frame)['artifact_ref']
        self.registry.put_artifact('test', 'evidence/input.json', b'{"fixture":true}', 'application/json')
        self.evidence_ref = self.registry.artifact_ref('test', 'evidence/input.json')
        self.calls = []; self.allowed = True
        self.ledger = HypothesisLedger(self.root / 'hypotheses.sqlite3')
        self.ledger.create('H-test', 'Synthetic research contract')
        self.graph = MerlinKnowledgeGraph(self.root / 'graph.sqlite3')
        self.outbox = MerlinEventOutbox(self.root / 'outbox.sqlite3')
        self.recorder = ResearchEvidenceRecorder(self.registry, self.ledger, self.graph)
        self.params = dict(project_id='test', session_id='session',
            branches=(Branch('a', 'Root', 2), Branch('b', 'Dependent', 1, ('a',))),
            source_commit=self.frame['source_commit'], research_plan_ref=self.frame_ref,
            principal='synthetic-host', executor_id='synthetic-check', executor_sha256='a' * 64,
            frame_validator=_validated_plan, approval=lambda _: self.allowed, lease=lambda _: True)
        self.session = RegistryBranchSession(self.registry, **self.params)
        self.handlers = self.make_handlers(build_branch_research_executor(self.session, self.evaluate))
        self.worker = self.make_worker()

    def evaluate(self, key, intent):
        self.calls.append(key)
        return {'passed': True, 'detail': key, 'artifact_refs': [deepcopy(self.evidence_ref)]}

    def make_handlers(self, executor):
        def unused(*_): raise AssertionError('unselected stage')
        return build_hermes_stage_handlers(evidence_recorder=self.recorder, project_id='test',
            research_executor=executor, numerical_experiment_executor=unused, proof_search_executor=unused,
            artifact_verifier=None, repository='Mannyspiro/expert-robot',
            commit_sha=self.frame['source_commit'], requester_id='synthetic-host')

    def make_worker(self, **changes):
        values = dict(handlers=self.handlers, approval_validator=lambda *_: self.allowed,
            lease_validator=lambda *_: True, worker_id='synthetic-worker', retry_delay_seconds=0,
            artifact_ref_validator=lambda ref: self.registry.resolve_artifact_ref(ref)['verified'])
        return HermesWorker(self.outbox, **{**values, **changes})

    def task(self, task_id='tick-1', **changes):
        return {'schema': 'merlin-research-task/2', 'task_id': task_id, 'hypothesis_id': 'H-test',
            'objective': 'Run one bounded synthetic branch check', 'stage': 'research',
            'approval_ref': 'synthetic-approval', 'lease_ref': 'synthetic-lease',
            'resource_budget': {'cpu_cores': 1, 'memory_bytes': 128 * 1024 * 1024,
                'max_wall_seconds': 30, 'compute_budget_units': 1},
            'artifact_refs': [deepcopy(self.frame_ref)], 'authority': 'bounded_execution_only',
            'promotion_authority': False, **changes}

    def enqueue(self, task=None, key='queue-1'):
        return self.outbox.enqueue(key, HERMES_TASK_TOPIC, task or self.task())

    def test_actual_worker_records_canonical_outcome_and_acknowledges(self):
        event = self.enqueue(); result = self.worker.run_once()
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(self.outbox.get(event['event_id'])['state'], 'acknowledged')
        self.assertEqual(self.calls, ['a']); self.assertEqual(self.ledger.get('H-test').status, 'proposed')
        self.assertEqual(result['receipt']['result']['cace_verification']['verification_status'], 'blocked_missing_credentials')
        self.assertIsNone(self.worker.run_once())

    def test_retry_before_ack_preserves_original_tick(self):
        event = self.enqueue(); receipts = []
        def fail_ack(*args, **kwargs):
            receipts.append(deepcopy(kwargs['result']))
            raise OSError('synthetic failure before acknowledgement')
        with patch.object(self.outbox, 'acknowledge', side_effect=fail_ack):
            self.assertEqual(self.worker.run_once()['status'], 'pending')
        self.assertEqual(self.calls, ['a'])
        replay = self.worker.run_once(); self.assertEqual(replay['status'], 'completed')
        self.assertEqual(self.calls, ['a'], 'one task retry must not advance another branch')
        self.assertEqual(replay['receipt'], receipts[0])
        self.assertEqual(len(self.ledger.evidence('H-test')), 1)
        self.assertEqual(self.outbox.get(event['event_id'])['attempts'], 2)

    def test_truthy_non_boolean_approval_is_rejected(self):
        self.enqueue(); result = self.make_worker(approval_validator=lambda *_: 1).run_once()
        self.assertEqual(result['status'], 'rejected'); self.assertEqual(self.calls, [])

    def test_truthy_non_boolean_lease_is_rejected(self):
        self.enqueue(); result = self.make_worker(lease_validator=lambda *_: {'allowed': True}).run_once()
        self.assertEqual(result['status'], 'rejected'); self.assertEqual(self.calls, [])

    def test_duplicate_delivery_same_task_replays_without_advancing(self):
        self.enqueue(); first = self.worker.run_once(); self.enqueue(key='duplicate-envelope')
        replay = self.worker.run_once(); self.assertEqual(first['receipt'], replay['receipt'])
        self.assertEqual(self.calls, ['a']); self.assertEqual(len(self.ledger.evidence('H-test')), 1)

    def test_distinct_task_advances_but_old_task_replays_old_snapshot(self):
        self.enqueue(); first = self.worker.run_once()
        self.enqueue(self.task('tick-2'), key='queue-2'); second = self.worker.run_once()
        self.assertEqual(second['receipt']['result']['metadata']['branch_state']['completed'], 2)
        self.enqueue(key='old-task-new-delivery'); replay = self.worker.run_once()
        self.assertEqual(replay['receipt'], first['receipt']); self.assertEqual(self.calls, ['a', 'b'])
        self.assertEqual(len(self.ledger.evidence('H-test')), 2)

    def test_changed_task_inputs_cannot_reuse_tick_identity(self):
        self.enqueue(); self.worker.run_once()
        self.enqueue(self.task(objective='Changed objective'), key='changed-inputs')
        self.assertNotEqual(self.worker.run_once()['status'], 'completed'); self.assertEqual(self.calls, ['a'])

    def test_boolean_integer_task_metadata_are_distinct(self):
        self.enqueue(self.task(experiment_spec={'flag': True})); self.worker.run_once()
        self.enqueue(self.task(experiment_spec={'flag': 1}), key='type-confusion')
        self.assertNotEqual(self.worker.run_once()['status'], 'completed'); self.assertEqual(self.calls, ['a'])

    def test_same_task_cannot_switch_sessions(self):
        self.enqueue(); self.worker.run_once()
        other = RegistryBranchSession(self.registry, **{**self.params, 'session_id': 'other'})
        handlers = self.make_handlers(build_branch_research_executor(other, self.evaluate))
        self.enqueue(key='other-session')
        self.assertNotEqual(self.make_worker(handlers=handlers).run_once()['status'], 'completed')
        self.assertEqual(self.calls, ['a']); self.assertEqual(other.status()['completed'], 0)

    def test_same_task_cannot_change_tick_budget(self):
        self.enqueue(); self.worker.run_once()
        handlers = self.make_handlers(build_branch_research_executor(self.session, self.evaluate, budget=2))
        self.enqueue(key='other-budget')
        self.assertNotEqual(self.make_worker(handlers=handlers).run_once()['status'], 'completed')
        self.assertEqual(self.calls, ['a'])

    def test_revoked_approval_blocks_even_completed_task_replay(self):
        self.enqueue(); self.worker.run_once(); self.allowed = False; self.enqueue(key='revoked-replay')
        self.assertEqual(self.worker.run_once()['status'], 'rejected'); self.assertEqual(self.calls, ['a'])

    def test_failed_parent_stays_blocking_through_real_worker(self):
        def failed(key, intent): return {**self.evaluate(key, intent), 'passed': False}
        self.handlers = self.make_handlers(build_branch_research_executor(self.session, failed)); self.worker = self.make_worker()
        self.enqueue(); first = self.worker.run_once(); state = first['receipt']['result']['metadata']['branch_state']
        self.assertEqual(state['branches'], [{'id': 'a', 'status': 'failed_local_check'}, {'id': 'b', 'status': 'waiting'}])
        self.enqueue(self.task('tick-2'), key='queue-2'); self.assertEqual(self.worker.run_once()['status'], 'completed')
        self.assertEqual(self.calls, ['a']); self.assertEqual(self.ledger.get('H-test').status, 'proposed')

    def test_interrupted_task_does_not_auto_repeat_effect(self):
        def interrupted(key, intent):
            self.calls.append(key); raise OSError('synthetic interrupted evaluator')
        handlers = self.make_handlers(build_branch_research_executor(self.session, interrupted)); self.enqueue()
        self.assertEqual(self.make_worker(handlers=handlers).run_once()['status'], 'pending')
        self.assertNotEqual(self.worker.run_once()['status'], 'completed'); self.assertEqual(self.calls, ['a'])
        self.assertEqual(self.session.status()['reconciliation_required'], 'a')

    def test_failure_after_outcome_before_task_result_fails_closed(self):
        original = self.session._put_path
        def fail_result(path, body):
            if path.startswith('branch-research-tasks/') and path.endswith('/result.json'): raise OSError('synthetic task result publication failure')
            return original(path, body)
        self.enqueue()
        with patch.object(self.session, '_put_path', side_effect=fail_result): self.assertEqual(self.worker.run_once()['status'], 'pending')
        self.assertNotEqual(self.worker.run_once()['status'], 'completed'); self.assertEqual(self.calls, ['a'])
        self.assertEqual(self.session.status()['completed'], 1)

    def test_projection_failure_after_task_checkpoint_replays_exact_result(self):
        self.enqueue()
        with patch.object(self.recorder, 'record_existing_artifact', side_effect=OSError('projection unavailable')): self.assertEqual(self.worker.run_once()['status'], 'pending')
        result = self.worker.run_once(); self.assertEqual(result['status'], 'completed'); self.assertEqual(self.calls, ['a'])
        self.assertEqual(result['receipt']['result']['metadata']['branch_state']['completed'], 1)
        self.assertEqual(len(self.ledger.evidence('H-test')), 1)

    def test_tampered_snapshot_blocks_replay_without_work(self):
        self.enqueue(); result = self.worker.run_once(); ref = result['receipt']['output_artifact_refs'][0]; checksum = ref['sha256']
        (self.registry.blobs / checksum[:2] / checksum[2:]).write_bytes(b'tampered'); self.enqueue(key='tampered-replay')
        self.assertNotEqual(self.worker.run_once()['status'], 'completed'); self.assertEqual(self.calls, ['a'])

    def test_mutating_approval_input_does_not_rewrite_admitted_task(self):
        task = self.task()
        def approval(ref, incoming):
            incoming['objective'] = 'not the admitted task'; incoming['resource_budget']['max_wall_seconds'] = 999
            incoming['artifact_refs'].clear(); return True
        self.enqueue(task); result = self.make_worker(approval_validator=approval).run_once()
        self.assertEqual(result['status'], 'completed'); self.assertEqual(result['receipt']['input_artifact_refs'], task['artifact_refs'])
        self.assertEqual(self.calls, ['a'])

    def test_mutating_lease_budget_does_not_change_context(self):
        observed = []; original = self.handlers['research']
        def lease(ref, budget): budget['max_wall_seconds'] = 999; return True
        def handler(task, context): observed.append(dict(context.resource_budget)); return original(task, context)
        self.enqueue(); self.make_worker(lease_validator=lease, handlers={'research': handler}).run_once()
        self.assertEqual(observed[0], self.task()['resource_budget'])

    def test_mutating_handler_and_context_inputs_does_not_rewrite_receipt(self):
        def handler(task, context):
            task['task_id'] = 'wrong-task'; task['hypothesis_id'] = 'wrong-hypothesis'; task['artifact_refs'].clear(); context.artifact_refs[0].clear()
            return {'artifact_refs': [deepcopy(self.evidence_ref)], 'evidence_refs': []}
        original = self.task(); self.enqueue(original); result = self.make_worker(handlers={'research': handler}).run_once()
        self.assertEqual(result['status'], 'completed')
        for k in ['task_id', 'hypothesis_id']: self.assertEqual(result['receipt'][k], original[k])
        self.assertEqual(result['receipt']['input_artifact_refs'], original['artifact_refs'])

    def test_reference_validator_mutation_does_not_rewrite_inputs_or_outputs(self):
        def validate(ref): ref.clear(); return True
        self.enqueue(); result = self.make_worker(artifact_ref_validator=validate).run_once()
        self.assertEqual(result['status'], 'completed'); self.assertEqual(result['receipt']['input_artifact_refs'], [self.frame_ref])
        for ref in result['receipt']['output_artifact_refs']: self.assertTrue(self.registry.resolve_artifact_ref(ref)['verified'])

    def test_truthy_reference_validator_does_not_admit_work(self):
        self.enqueue(); result = self.make_worker(artifact_ref_validator=lambda _: 1).run_once()
        self.assertNotEqual(result['status'], 'completed'); self.assertEqual(self.calls, [])

    def test_cancellation_after_task_intent_blocks_evaluator(self):
        event = self.enqueue(); original = self.session._put_path
        def cancel_after_intent(path, body):
            ref = original(path, body)
            if path.startswith('branch-research-tasks/') and path.endswith('/request.json'): self.outbox.cancel(event['event_id'], 'synthetic-operator')
            return ref
        with patch.object(self.session, '_put_path', side_effect=cancel_after_intent): self.assertEqual(self.worker.run_once()['status'], 'cancelled')
        self.assertEqual(self.calls, []); self.assertEqual(self.session.status()['completed'], 0)

    def test_worker_lease_loss_after_task_intent_blocks_evaluator(self):
        original = self.session._put_path; self.enqueue()
        def lose_lease(path, body):
            ref = original(path, body)
            if path.startswith('branch-research-tasks/') and path.endswith('/request.json'): raise LeaseConflict('synthetic loss after task intent')
            return ref
        with patch.object(self.session, '_put_path', side_effect=lose_lease): self.assertEqual(self.worker.run_once()['status'], 'lease_lost')
        self.assertEqual(self.calls, [])

    def test_process_death_before_ack_reclaims_exact_task_result(self):
        settings = {'frame': self.frame, 'frame_ref': self.frame_ref, 'evidence_ref': self.evidence_ref}
        (self.root / 'settings.json').write_text(json.dumps(settings)); event = self.enqueue()
        code = r'''
import json,os,sys
from pathlib import Path
from merlin.branch_research import Branch
from merlin.branch_registry import RegistryBranchSession,build_branch_research_executor
from merlin.project_registry import MerlinRegistry
from merlin.event_outbox import MerlinEventOutbox
from merlin.hermes_worker import HermesWorker
from merlin.hermes_stage_handlers import build_hermes_stage_handlers
from merlin.research_evidence import ResearchEvidenceRecorder
from merlin.hypothesis_ledger import HypothesisLedger
from merlin.knowledge_graph import MerlinKnowledgeGraph
from dot_ai_os.research_protocol import _validated_plan
root=Path(sys.argv[1]);cfg=json.loads((root/'settings.json').read_text())
r=MerlinRegistry(root/'registry');o=MerlinEventOutbox(root/'outbox.sqlite3')
l=HypothesisLedger(root/'hypotheses.sqlite3');g=MerlinKnowledgeGraph(root/'graph.sqlite3')
s=RegistryBranchSession(r,project_id='test',session_id='session',branches=(Branch('a','Root',2),Branch('b','Dependent',1,('a',))),source_commit=cfg['frame']['source_commit'],research_plan_ref=cfg['frame_ref'],principal='synthetic-host',executor_id='synthetic-check',executor_sha256='a'*64,frame_validator=_validated_plan,approval=lambda _:True,lease=lambda _:True)
def evaluate(key,intent):
 with (root/'effects.txt').open('a') as f:f.write(key+'\n');f.flush();os.fsync(f.fileno())
 return {'passed':True,'detail':key,'artifact_refs':[cfg['evidence_ref']]}
def unused(*_):raise AssertionError('wrong stage')
h=build_hermes_stage_handlers(evidence_recorder=ResearchEvidenceRecorder(r,l,g),project_id='test',research_executor=build_branch_research_executor(s,evaluate),numerical_experiment_executor=unused,proof_search_executor=unused,artifact_verifier=None,repository='Mannyspiro/expert-robot',commit_sha=cfg['frame']['source_commit'],requester_id='synthetic-host')
def die(*args,**kwargs):os._exit(73)
o.acknowledge=die
w=HermesWorker(o,handlers=h,approval_validator=lambda *_:True,lease_validator=lambda *_:True,worker_id='synthetic-child',lease_seconds=0.1,artifact_ref_validator=lambda ref:r.resolve_artifact_ref(ref)['verified'])
w.run_once()
'''
        source = Path(__file__).resolve().parents[1] / 'python'
        child = subprocess.run([sys.executable, '-B', '-c', code, str(self.root)], env={'PATH': os.defpath, 'PYTHONPATH': str(source)}, capture_output=True, text=True, timeout=15)
        self.assertEqual(child.returncode, 73, child.stderr)
        self.assertEqual((self.root / 'effects.txt').read_text().splitlines(), ['a']); time.sleep(0.15)
        result = self.worker.run_once(); self.assertEqual(result['status'], 'completed'); self.assertEqual(self.calls, [])
        self.assertEqual(result['receipt']['result']['metadata']['branch_state']['completed'], 1)
        self.assertEqual(self.outbox.get(event['event_id'])['attempts'], 2); self.assertEqual(len(self.ledger.evidence('H-test')), 1)


if __name__ == '__main__': unittest.main()
