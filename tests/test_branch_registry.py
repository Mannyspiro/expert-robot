"""Synthetic canonical-store/actual-Hermes-handler checks, not provider validation."""
from contextlib import closing
from copy import deepcopy
from dataclasses import replace
import fcntl
import itertools
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from merlin.branch_research import Branch, BranchResearch, canonical, digest
from merlin.branch_registry import RegistryBranchSession, BranchSessionConflict, build_branch_research_executor
from merlin.project_registry import MerlinRegistry
from dot_ai_os.research_protocol import research_episode_demo, store_research_record, _validated_plan
from merlin.hermes_stage_handlers import build_hermes_stage_handlers
from merlin.research_evidence import ResearchEvidenceRecorder
from merlin.hypothesis_ledger import HypothesisLedger
from merlin.knowledge_graph import MerlinKnowledgeGraph

PLAN = (Branch('a', 'Root A', 5), Branch('b', 'Root B', 4),
        Branch('join', 'Join', 8, ('a', 'b')),
        Branch('explore', 'Explore', 1, ('b',), True),
        Branch('finish', 'Finish', 3, ('join', 'explore')))
PAIR = (PLAN[0], Branch('child', 'Child', 1, ('a',)))


class RegistryBranchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = research_episode_demo({})['research_plan']

    def setUp(self):
        self.tmp = TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.registry = MerlinRegistry(self.root / 'registry')
        self.registry.register_project('test', 'Synthetic test')
        self.frame_ref = store_research_record(self.registry, 'test', self.frame)['artifact_ref']
        self.registry.put_artifact('test', 'evidence/input.json', b'{"fixture":true}', 'application/json')
        self.evidence_ref = self.registry.artifact_ref('test', 'evidence/input.json')
        self.allowed = True
        self.calls = []
        self.params = dict(project_id='test', session_id='session', branches=PLAN,
                           source_commit=self.frame['source_commit'], research_plan_ref=self.frame_ref,
                           principal='synthetic-host', executor_id='synthetic-check', executor_sha256='a'*64,
                           frame_validator=_validated_plan, approval=lambda _:self.allowed, lease=lambda _:True)

    def session(self, **changes):
        return RegistryBranchSession(self.registry, **{**self.params, **changes})

    def evaluate(self, key, intent):
        self.calls.append(key)
        return {'passed': True, 'detail': key, 'artifact_refs': [deepcopy(self.evidence_ref)]}

    def step(self, session=None, evaluate=None, **options):
        return (session or self.session()).step(evaluate or self.evaluate, check_cancelled=lambda:None, **options)

    def test_resume_exact_refs_and_no_second_database(self):
        self.step(budget=2); resumed=self.step(budget=4)
        self.assertEqual(self.calls, ['a','b','explore','join','finish'])
        self.assertEqual(resumed, self.step(budget=4))
        self.assertEqual(len(self.calls),5)
        databases=list(self.root.rglob('*.sqlite3'))
        self.assertEqual(len(databases),1)
        for ref in resumed['outcome_refs']:
            self.assertTrue(self.registry.resolve_artifact_ref(ref)['verified'])
        self.assertFalse(resumed['qualification']);self.assertFalse(resumed['promotion_authority'])

    def test_all_32_five_branch_outcomes_match_standalone_policy(self):
        for bits in itertools.product((False,True),repeat=5):
            case='case-'+''.join(str(int(bit)) for bit in bits)
            values=dict(zip((b.id for b in PLAN),bits));left=[];right=[]
            old=BranchResearch(self.root/(case+'.sqlite3'),PLAN)
            def baseline(key,inputs):
                left.append(key);return {'passed':values[key],'detail':key}
            new=self.session(session_id=case)
            def candidate(key,intent):
                right.append(key);return {**self.evaluate(key,intent),'passed':values[key]}
            old.step(baseline,budget=2);old_result=old.step(baseline,budget=4)
            self.step(new,candidate,budget=2);new_result=self.step(new,candidate,budget=4)
            self.assertEqual(left,right,(case,left,right))
            self.assertEqual(new_result,self.step(new,candidate,budget=4))
            self.assertEqual(old_result['progression']['completed'],sum(x['status']=='passed_local_check' for x in new_result['branches']))

    def test_failed_parent_blocks_dependents(self):
        def fail(key,intent):return {**self.evaluate(key,intent),'passed':key!='a'}
        result=self.step(evaluate=fail,budget=4)
        self.assertEqual(self.calls,['a','b','explore'])
        self.assertIsNone(result['selected'])
        self.assertEqual(result['branches'][-1]['status'],'waiting')

    def test_callback_cannot_mutate_lineage(self):
        def mutate(key,intent):
            intent['plan_ref'].clear();intent['prerequisite_refs'].clear();intent['executor']['sha256']='b'*64
            return self.evaluate(key,intent)
        session=self.session();self.step(session,mutate,budget=4)
        result=self.step(session,mutate,budget=4)
        self.assertEqual(result['completed'],5)
        self.assertEqual(session.spec['executor']['sha256'],'a'*64)
        self.assertEqual(self.session().status(),result)

    def test_callback_error_retains_intent_and_does_not_repeat(self):
        def broken(key,intent):self.calls.append(key);raise RuntimeError('synthetic fault')
        with self.assertRaises(RuntimeError):self.step(evaluate=broken)
        self.assertEqual(self.step()['reconciliation_required'],'a')
        self.assertEqual(self.calls,['a'])
        failure=json.loads(self.registry.read_artifact_ref(self.registry.artifact_ref('test','branch-research/session/failures/a.json'))['content'])
        self.assertEqual(failure['error_class'],'RuntimeError')

    def test_process_exit_after_effect_is_not_automatically_retried(self):
        settings={k:v for k,v in self.params.items() if k not in {'branches','frame_validator','approval','lease'}}
        config=self.root/'settings.json';config.write_text(json.dumps(settings))
        marker=self.root/'effect.txt'
        code='''import json,os,sys
from pathlib import Path
from merlin.project_registry import MerlinRegistry
from merlin.branch_registry import RegistryBranchSession
from merlin.branch_research import Branch
from dot_ai_os.research_protocol import _validated_plan
p=json.loads(Path(sys.argv[2]).read_text());p.update(branches=(Branch('a','Root A',5),),frame_validator=_validated_plan,approval=lambda _:True,lease=lambda _:True)
s=RegistryBranchSession(MerlinRegistry(sys.argv[1]),**p)
def crash(key,intent):
 Path(sys.argv[3]).write_text('effect-performed');os._exit(73)
s.step(crash,check_cancelled=lambda:None)
'''
        root=Path(__file__).resolve().parents[1]
        result=subprocess.run([sys.executable,'-B','-c',code,str(self.registry.root),str(config),str(marker)],
                              env={**os.environ,'PYTHONPATH':str(root/'python')},capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,73,result.stderr)
        restored=self.session(branches=(PLAN[0],))
        self.assertEqual(self.step(restored)['reconciliation_required'],'a')
        self.assertEqual(self.calls,[]);self.assertEqual(marker.read_text(),'effect-performed')

    def test_publish_error_after_effect_requires_reconciliation(self):
        original=self.registry.put_artifact
        def failing(project,path,*args,**kwargs):
            if '/outcomes/' in path:raise OSError('synthetic publication failure')
            return original(project,path,*args,**kwargs)
        with patch.object(self.registry,'put_artifact',side_effect=failing):
            with self.assertRaises(OSError):self.step()
        self.assertEqual(self.step()['reconciliation_required'],'a');self.assertEqual(self.calls,['a'])

    def test_projection_failure_replays_without_repeating_callback(self):
        with patch.object(self.registry,'relate',side_effect=OSError('projection failure')):
            with self.assertRaises(OSError):self.step()
        result=self.step(budget=4)
        self.assertEqual(result['completed'],5);self.assertEqual(self.calls.count('a'),1)

    def test_distinct_paths_with_same_digest_remain_distinct(self):
        self.registry.put_artifact('test','evidence/alias.json',b'{"fixture":true}','application/json')
        alias=self.registry.artifact_ref('test','evidence/alias.json')
        def two(key,intent):return {**self.evaluate(key,intent),'artifact_refs':[self.evidence_ref,alias]}
        result=self.step(evaluate=two)
        body=json.loads(self.registry.read_artifact_ref(result['outcome_refs'][0])['content'])
        self.assertEqual(len(body['evidence']['artifact_refs']),2)
        self.assertNotEqual(body['evidence']['artifact_refs'][0],body['evidence']['artifact_refs'][1])

    def test_changed_bindings_rejected_before_call(self):
        self.step()
        variants=[{'principal':'other'},{'executor_sha256':'b'*64},{'executor_id':'different'},
                  {'branches':tuple(replace(b,title='changed') if b.id=='a' else b for b in PLAN)}]
        for change in variants:
            with self.subTest(change=change),self.assertRaises(BranchSessionConflict):self.step(self.session(**change))
        self.assertEqual(self.calls,['a'])

    def test_wrong_source_frame_is_rejected(self):
        with self.assertRaises(ValueError):self.session(source_commit='b'*40)
        self.assertEqual(self.calls,[])

    def test_rehashed_invalid_frame_is_not_validation(self):
        from dot_ai_os.bridge import canonical as canon_bytes,digest as byte_digest
        frame=deepcopy(self.frame);frame['qualification']=True
        frame['record_sha256']=byte_digest(canon_bytes({k:v for k,v in frame.items() if k!='record_sha256'}))
        self.registry.put_artifact('test','invalid-frame.json',canon_bytes(frame),'application/json')
        with self.assertRaises(ValueError):self.session(research_plan_ref=self.registry.artifact_ref('test','invalid-frame.json'))

    def test_cross_project_frame_is_rejected(self):
        self.registry.register_project('other','Other')
        ref=store_research_record(self.registry,'other',self.frame)['artifact_ref']
        with self.assertRaises(ValueError):self.session(research_plan_ref=ref)

    def test_approval_and_lease_require_literal_true(self):
        for value in (False,1,'yes',None):
            for field in ('approval','lease'):
                with self.subTest(value=value,field=field),self.assertRaises(PermissionError):
                    self.step(self.session(**{field:lambda _,v=value:v}))
        self.assertEqual(self.calls,[])
        self.assertFalse(self.registry.artifact_history('test','branch-research/session/plan.json'))

    def test_revoked_after_effect_stops_before_commit(self):
        def revoke(key,intent):
            result=self.evaluate(key,intent);self.allowed=False;return result
        with self.assertRaises(PermissionError):self.step(evaluate=revoke)
        self.allowed=True
        self.assertEqual(self.step()['reconciliation_required'],'a');self.assertEqual(self.calls,['a'])

    def test_invalid_outcomes_require_reconciliation(self):
        bad=[None,{}, {'passed':1,'detail':'x','artifact_refs':[self.evidence_ref]},
             {'passed':True,'detail':'x','artifact_refs':[]},
             {'passed':True,'detail':'x','artifact_refs':[self.evidence_ref]*2},
             {'passed':True,'detail':'x','artifact_refs':[self.evidence_ref],'qualification':True}]
        for i,value in enumerate(bad):
            s=self.session(session_id='bad-'+str(i))
            with self.subTest(i=i),self.assertRaises(ValueError):self.step(s,lambda *_:value)
            self.assertEqual(self.step(s)['reconciliation_required'],'a')
        self.assertEqual(self.calls,[])

    def test_cross_project_outcome_requires_reconciliation(self):
        self.registry.register_project('other','Other');self.registry.put_artifact('other','x',b'x')
        foreign=self.registry.artifact_ref('other','x')
        with self.assertRaises(ValueError):self.step(evaluate=lambda *_:{'passed':True,'detail':'x','artifact_refs':[foreign]})
        self.assertEqual(self.step()['reconciliation_required'],'a')

    def test_status_mutations_do_not_change_persistence(self):
        result=self.step();expected=deepcopy(result);result['outcome_refs'][0].clear()
        self.assertEqual(self.session().status(),expected)

    def test_extra_version_of_session_record_is_rejected(self):
        self.step();self.registry.put_artifact('test','branch-research/session/plan.json',b'{}','application/json')
        with self.assertRaises(BranchSessionConflict):self.step()
        self.assertEqual(self.calls,['a'])

    def test_evidence_blob_tamper_blocks_replay(self):
        self.step();sha=self.evidence_ref['sha256'];(self.registry.blobs/sha[:2]/sha[2:]).write_bytes(b'tamper')
        with self.assertRaises(RuntimeError):self.step()
        self.assertEqual(self.calls,['a'])

    def test_orphan_outcome_fails_closed(self):
        self.registry.put_artifact('test','branch-research/session/outcomes/a.json',b'{}','application/json')
        with self.assertRaises(BranchSessionConflict):self.step()
        self.assertEqual(self.calls,[])

    def test_out_of_order_intent_fails_closed(self):
        self.step()
        self.registry.put_artifact('test','branch-research/session/intents/finish.json',b'{}','application/json')
        with self.assertRaises(BranchSessionConflict):self.step()
        self.assertEqual(self.calls,['a'])

    def test_snapshot_idempotent_and_gated(self):
        self.step();s=self.session();ref=s.snapshot();self.assertEqual(ref,s.snapshot())
        self.allowed=False
        with self.assertRaises(PermissionError):s.snapshot()

    def test_cooperative_lock_prevents_concurrent_call(self):
        with (self.registry.root/'dot-dual-coder.lock').open('a') as stream:
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BranchSessionConflict):self.step()
        self.assertEqual(self.calls,[])

    def test_backup_restore_exact_refs_no_duplicate_callback(self):
        before=self.step(budget=2);target=self.root/'restored';target.mkdir()
        for db in self.registry.root.glob('*.sqlite3'):
            with closing(sqlite3.connect(db)) as src,closing(sqlite3.connect(target/db.name)) as dst:src.backup(dst)
        shutil.copytree(self.registry.blobs,target/self.registry.blobs.relative_to(self.registry.root))
        restored=MerlinRegistry(target);session=RegistryBranchSession(restored,**self.params)
        self.assertEqual(session.status(),before)
        result=self.step(session,budget=4);self.assertEqual(result['completed'],5)
        self.assertEqual(self.calls,['a','b','explore','join','finish'])

    def test_invalid_budget_does_not_call_evaluator(self):
        for budget in (0,5,True,1.0,'1',None):
            with self.subTest(budget=budget),self.assertRaises(ValueError):self.step(budget=budget)
        self.assertEqual(self.calls,[])

    def test_invalid_catalogue_rejected_before_mutation(self):
        variants=[(),(PLAN[0],PLAN[0]),(Branch('a','A',1,('missing',)),),
                  (Branch('a','A',1,('a',)),),(replace(PLAN[0],priority=True),),
                  (replace(PLAN[0],exploratory=1),),(replace(PLAN[0],prerequisites=[]),)]
        for branches in variants:
            with self.subTest(branches=branches),self.assertRaises(ValueError):self.session(branches=branches)

    def test_cancel_before_intent_does_not_execute(self):
        def cancel():raise InterruptedError('cancelled')
        with self.assertRaises(InterruptedError):self.session().step(self.evaluate,check_cancelled=cancel)
        self.assertEqual(self.calls,[])
        self.assertFalse(self.registry.artifact_history('test','branch-research/session/plan.json'))

    def test_actual_hermes_stage_records_ref_and_preserves_hypothesis_status(self):
        ledger=HypothesisLedger(self.root/'hypotheses.sqlite3');ledger.create('H-test','Synthetic contract')
        graph=MerlinKnowledgeGraph(self.root/'graph.sqlite3');recorder=ResearchEvidenceRecorder(self.registry,ledger,graph)
        executor=build_branch_research_executor(self.session(branches=(PLAN[0],)),self.evaluate)
        def unused(*_):raise AssertionError('unselected executor')
        handlers=build_hermes_stage_handlers(evidence_recorder=recorder,project_id='test',
            research_executor=executor,numerical_experiment_executor=unused,proof_search_executor=unused,
            artifact_verifier=None,repository='Mannyspiro/expert-robot',commit_sha=self.params['source_commit'],requester_id='synthetic-host')
        context=SimpleNamespace(task_id='t1',hypothesis_id='H-test',artifact_refs=(self.frame_ref,),
            check_cancelled=lambda:None,emit_progress=lambda *a:None,emit_tool_event=lambda *a:None)
        result=handlers['research']({'stage':'research','task_id':'t1'},context)
        replay=handlers['research']({'stage':'research','task_id':'t1'},context)
        self.assertEqual(result['artifact']['artifact_ref'],replay['artifact']['artifact_ref'])
        self.assertEqual(result['cace_verification']['verification_status'],'blocked_missing_credentials')
        self.assertEqual(ledger.get('H-test').status,'proposed');self.assertEqual(len(ledger.evidence('H-test')),1)
        self.assertEqual(self.calls,['a'])
        self.assertFalse(result['metadata']['qualification'])

    def test_hermes_task_or_frame_mismatch_rejected(self):
        run=build_branch_research_executor(self.session(),self.evaluate)
        context=SimpleNamespace(task_id='t1',artifact_refs=(),check_cancelled=lambda:None)
        with self.assertRaises(ValueError):run({'task_id':'t1','stage':'research'},context)
        context.artifact_refs=(self.frame_ref,)
        with self.assertRaises(ValueError):run({'task_id':'t2','stage':'research'},context)
        with self.assertRaises(ValueError):run({'task_id':'t1','stage':'proof_search'},context)
        self.assertEqual(self.calls,[])


    def test_reserved_path_components_rejected(self):
        for value in ('.', '..'):
            for field in ('session_id', 'executor_id'):
                with self.subTest(value=value,field=field),self.assertRaises(ValueError):
                    self.session(**{field:value})
            with self.assertRaises(ValueError):self.session(branches=(replace(PLAN[0],id=value),))
        self.assertEqual(self.calls,[])

    def test_cancellation_after_intent_blocks_callback(self):
        session=self.session();published=False;original=session._put
        def put(suffix,body):
            nonlocal published
            ref=original(suffix,body)
            if suffix.startswith('intents/'):published=True
            return ref
        def cancelled():
            if published:raise InterruptedError('cancelled before dispatch')
        with patch.object(session,'_put',side_effect=put):
            with self.assertRaises(InterruptedError):session.step(self.evaluate,check_cancelled=cancelled)
        self.assertEqual(self.calls,[])
        self.assertEqual(self.step()['reconciliation_required'],'a')

    def test_hermes_snapshot_rejects_intervening_tick(self):
        session=self.session();original=session._step_locked
        def interleaved(*args,**kwargs):
            old=original(*args,**kwargs)
            original(self.evaluate,check_cancelled=lambda:None,budget=1)
            return old
        execute=build_branch_research_executor(session,self.evaluate)
        context=SimpleNamespace(task_id='t1',hypothesis_id='H-test',artifact_refs=(self.frame_ref,),check_cancelled=lambda:None)
        with patch.object(session,'_step_locked',side_effect=interleaved):
            with self.assertRaises(BranchSessionConflict):execute({'stage':'research','task_id':'t1'},context)
        self.assertEqual(session.status()['completed'],2)
        self.assertEqual(self.calls,['a','b'])

if __name__=='__main__':unittest.main()
