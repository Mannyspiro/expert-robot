"""Actual canonical worker/store recovery; authority is a synthetic fixture."""
import json
import unittest
from unittest.mock import patch
import test_branch_worker as fixtures
from merlin.branch_research import canonical, digest
from merlin.branch_registry import BranchSessionConflict, build_branch_research_executor
from merlin.branch_task_recovery import RecoverableBranchExecutor, guard_unfinished_tasks, task_path


class BranchTaskRecoveryTests(unittest.TestCase):
    evaluate = fixtures.BranchWorkerTests.evaluate
    make_handlers = fixtures.BranchWorkerTests.make_handlers
    make_worker = fixtures.BranchWorkerTests.make_worker
    task = fixtures.BranchWorkerTests.task
    enqueue = fixtures.BranchWorkerTests.enqueue

    def setUp(self):
        fixtures.BranchWorkerTests.setUp(self)
        self.recovery_allowed = True
        self.executor = RecoverableBranchExecutor(self.session, self.evaluate,
            recovery_authorizer=lambda *_: self.recovery_allowed)
        self.handlers = self.make_handlers(self.executor); self.worker = self.make_worker()

    def interrupt(self, before=False):
        self.enqueue()
        obj, name = (self.session, '_step_locked') if before else (self.executor, '_publish')
        with patch.object(obj, name, side_effect=OSError('synthetic interruption')):
            self.assertEqual(self.worker.run_once()['status'], 'pending')
        self.assertEqual(self.calls, [] if before else ['a'])

    def decision(self, *, action='publish_committed_outcomes_only', name='review', **changes):
        body = {'schema':'merlin-branch-recovery-decision/1',
            'request_ref':self.registry.artifact_ref('test', task_path('tick-1')+'request.json'),
            'expected_state_sha256':digest(self.session.status()), 'action':action,
            'reviewer_id':'synthetic-operator', 'reason':'Synthetic exact-state review',
            'authority':'reconcile_only', 'qualification':False, 'promotion_authority':False, **changes}
        path='recovery-decisions/'+name+'.json'
        self.registry.put_artifact('test',path,canonical(body).encode(),'application/json')
        return self.registry.artifact_ref('test',path)

    def recover(self, ref):
        handler=lambda task,ctx:self.executor.reconcile(task,ctx,decision_ref=ref)
        return self.make_worker(handlers=self.make_handlers(handler)).run_once()

    def test_normal_tick_and_duplicate_have_exact_same_receipt(self):
        self.enqueue(); a=self.worker.run_once(); self.enqueue(key='duplicate'); b=self.worker.run_once()
        self.assertEqual(a['status'],'completed'); self.assertEqual(a['receipt'],b['receipt']); self.assertEqual(self.calls,['a'])

    def test_committed_outcome_recovers_without_repeating_evaluator(self):
        self.interrupt(); result=self.recover(self.decision())
        self.assertEqual(result['status'],'completed'); self.assertEqual(self.calls,['a'])
        ref=result['receipt']['result']['metadata']['task_recovery_ref']
        self.assertIs(json.loads(self.registry.read_artifact_ref(ref)['content'])['evaluator_reexecuted'],False)
        self.assertEqual(self.ledger.get('H-test').status,'proposed')
        self.assertEqual(result['receipt']['result']['cace_verification']['verification_status'],'blocked_missing_credentials')

    def test_successor_is_fenced_without_creating_a_second_reservation(self):
        self.interrupt(); self.enqueue(self.task('tick-2'),key='later')
        for _ in range(5): self.worker.run_once()
        self.assertEqual(self.calls,['a'])
        self.assertEqual(self.registry.artifact_history('test',task_path('tick-2')+'request.json'),[])

    def test_direct_tick_is_also_fenced(self):
        self.interrupt()
        with self.assertRaisesRegex(BranchSessionConflict,'unfinished'):
            self.session.step(self.evaluate,check_cancelled=lambda:None)
        self.assertEqual(self.calls,['a'])

    def test_legacy_executor_is_also_fenced(self):
        self.interrupt(); self.enqueue(self.task('tick-2'),key='legacy')
        worker=self.make_worker(handlers=self.make_handlers(build_branch_research_executor(self.session,self.evaluate)))
        for _ in range(5): worker.run_once()
        self.assertEqual(self.calls,['a'])

    def test_missing_outcome_is_not_invented_even_with_recovery_permission(self):
        def uncertain(key,intent): self.calls.append(key); raise OSError('effect outcome unknown')
        self.executor.evaluate=uncertain; self.enqueue(); self.worker.run_once()
        self.assertNotEqual(self.recover(self.decision())['status'],'completed')
        self.assertEqual(self.calls,['a']); self.assertEqual(self.session.status()['reconciliation_required'],'a')
        self.assertEqual(self.registry.artifact_history('test',task_path('tick-1')+'result.json'),[])

    def test_no_execution_can_be_closed_then_new_task_advances(self):
        self.interrupt(before=True)
        self.assertEqual(self.recover(self.decision(action='close_without_execution'))['status'],'completed')
        self.assertEqual(self.calls,[])
        self.enqueue(self.task('tick-2'),key='new'); self.worker.run_once(); self.assertEqual(self.calls,['a'])

    def test_noop_cannot_discard_committed_outcome(self):
        self.interrupt()
        self.assertNotEqual(self.recover(self.decision(action='close_without_execution'))['status'],'completed')
        self.assertEqual(self.calls,['a'])

    def test_publish_cannot_invent_an_unexecuted_outcome(self):
        self.interrupt(before=True)
        self.assertNotEqual(self.recover(self.decision())['status'],'completed'); self.assertEqual(self.calls,[])

    def test_missing_recovery_authorizer_rejected(self):
        self.interrupt(); self.executor.recovery_authorizer=None
        self.assertEqual(self.recover(self.decision())['status'],'rejected')

    def test_truthy_recovery_authorizer_rejected(self):
        self.interrupt(); self.executor.recovery_authorizer=lambda *_:1
        self.assertEqual(self.recover(self.decision())['status'],'rejected')

    def test_revoked_recovery_permission_rejected(self):
        self.interrupt(); self.recovery_allowed=False
        self.assertEqual(self.recover(self.decision())['status'],'rejected')

    def test_revoked_normal_approval_rejected(self):
        self.interrupt(); ref=self.decision(); self.allowed=False
        self.assertEqual(self.recover(ref)['status'],'rejected')

    def test_stale_review_fails_closed(self):
        self.interrupt()
        self.assertNotEqual(self.recover(self.decision(expected_state_sha256='0'*64))['status'],'completed')
        self.assertEqual(self.calls,['a'])

    def test_wrong_request_binding_fails_closed(self):
        self.interrupt()
        self.assertNotEqual(self.recover(self.decision(request_ref=self.evidence_ref))['status'],'completed')

    def test_authority_escalation_is_rejected(self):
        self.interrupt()
        self.assertNotEqual(self.recover(self.decision(promotion_authority=True))['status'],'completed')

    def test_authorizer_mutation_cannot_rewrite_decision(self):
        self.interrupt()
        def mutate(ref,decision): ref.clear(); decision.clear(); return True
        self.executor.recovery_authorizer=mutate
        self.assertEqual(self.recover(self.decision())['status'],'completed'); self.assertEqual(self.calls,['a'])

    def test_recovery_publication_interruption_can_resume_idempotently(self):
        self.interrupt(); ref=self.decision(); original=self.session._put_path
        def crash(path,body):
            if path.endswith('/result.json'): raise OSError('after recovery record')
            return original(path,body)
        with patch.object(self.session,'_put_path',side_effect=crash):
            self.assertEqual(self.recover(ref)['status'],'pending')
        self.assertEqual(self.recover(ref)['status'],'completed'); self.assertEqual(self.calls,['a'])
        for suffix in ('request.json','recovery.json','result.json'):
            self.assertEqual(len(self.registry.artifact_history('test',task_path('tick-1')+suffix)),1)

    def test_different_decision_cannot_replace_bound_recovery(self):
        self.interrupt(); first=self.decision()
        with patch.object(self.executor,'_publish',side_effect=OSError('during recovery')): self.recover(first)
        self.assertNotEqual(self.recover(self.decision(name='other',reason='different decision'))['status'],'completed')
        self.assertEqual(self.calls,['a'])

    def test_old_task_replays_exact_recovered_result_after_successor(self):
        self.interrupt(); first=self.recover(self.decision())
        self.enqueue(self.task('tick-2'),key='next'); self.worker.run_once()
        self.enqueue(key='old'); result=self.worker.run_once()
        self.assertEqual(first['receipt'],result['receipt']); self.assertEqual(self.calls,['a','b'])

    def test_repeated_recovery_after_successor_replays_original_result(self):
        self.interrupt(); ref=self.decision(); first=self.recover(ref)
        self.enqueue(self.task('tick-2'),key='next'); self.worker.run_once()
        self.enqueue(key='repeat-review'); result=self.recover(ref)
        self.assertEqual(first['receipt'],result['receipt']); self.assertEqual(self.calls,['a','b'])

    def test_tampered_decision_bytes_block_recovery(self):
        self.interrupt(); ref=self.decision()
        (self.registry.blobs/ref['sha256'][:2]/ref['sha256'][2:]).write_bytes(b'{}')
        self.assertNotEqual(self.recover(ref)['status'],'completed'); self.assertEqual(self.calls,['a'])

    def test_changed_task_budget_does_not_reuse_identity(self):
        self.enqueue(); self.worker.run_once(); task=self.task(); task['resource_budget']['compute_budget_units']=2
        self.enqueue(task,key='changed'); self.assertNotEqual(self.worker.run_once()['status'],'completed')
        self.assertEqual(self.calls,['a'])

    def test_two_committed_branches_recover_without_repeating_either(self):
        self.executor.budget=2; self.enqueue()
        with patch.object(self.executor,'_publish',side_effect=OSError('after two outcomes')): self.worker.run_once()
        self.assertEqual(self.calls,['a','b'])
        result=self.recover(self.decision()); self.assertEqual(result['status'],'completed')
        self.assertEqual(result['receipt']['result']['metadata']['branch_state']['completed'],2)
        self.assertEqual(self.calls,['a','b'])

    def test_ambiguous_second_effect_blocks_whole_tick_recovery(self):
        self.executor.budget=2
        def evaluate(key,intent):
            value=self.evaluate(key,intent)
            if key=='b': raise OSError('unknown second effect')
            return value
        self.executor.evaluate=evaluate; self.enqueue(); self.worker.run_once()
        self.assertNotEqual(self.recover(self.decision())['status'],'completed')
        self.assertEqual(self.calls,['a','b']); self.assertEqual(self.session.status()['completed'],1)

    def test_legacy_request_start_is_not_guessed(self):
        self.handlers=self.make_handlers(build_branch_research_executor(self.session,self.evaluate)); self.worker=self.make_worker()
        self.enqueue(); original=self.session._put_path
        def crash(path,body):
            if path.endswith('/result.json'): raise OSError('legacy interruption')
            return original(path,body)
        with patch.object(self.session,'_put_path',side_effect=crash): self.worker.run_once()
        self.assertNotEqual(self.recover(self.decision())['status'],'completed'); self.assertEqual(self.calls,['a'])

    def test_guard_uses_bounded_query_not_inventory(self):
        with patch.object(self.registry,'inventory',side_effect=AssertionError('unbounded query')):
            self.enqueue(); self.assertEqual(self.worker.run_once()['status'],'completed')

    def test_guard_rejects_truncated_history(self):
        with patch.object(self.registry,'artifact_paths',return_value={'paths':[],'truncated':True}):
            with self.assertRaisesRegex(BranchSessionConflict,'ceiling'): guard_unfinished_tasks(self.session)

    def test_recovery_replay_cancellation_checked_after_projection(self):
        self.interrupt(); ref=self.decision(); self.recover(ref); event=self.enqueue(key='cancel-review')
        original=self.executor._replay
        def cancel(*args):
            answer=original(*args); self.outbox.cancel(event['event_id'],'synthetic-operator'); return answer
        with patch.object(self.executor,'_replay',side_effect=cancel): result=self.recover(ref)
        self.assertEqual(result['status'],'cancelled'); self.assertEqual(self.calls,['a'])

if __name__=='__main__': unittest.main()
