"""Build stopping contracts; synthetic host authentication, real canonical store."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from merlin.build_loop import BuildGoal, decide_build, record_build_decision
from merlin.branch_research import canonical
from merlin.project_registry import MerlinRegistry


class BuildLoopTests(unittest.TestCase):
    def setUp(self):
        self.goal = BuildGoal('a'*40, 'b'*64, 281, 2)
        binding = dict(source_commit=self.goal.source_commit, source_map_sha256=self.goal.source_map_sha256,
                       qualification=False, promotion_authority=False)
        self.pub = dict(binding, status='observed', branch_head=self.goal.source_commit, readback_complete=True)
        self.sw = dict(binding, status='succeeded', tests=281, failures=0, errors=0, skipped=0, passed=True, run_id=123)
        self.kr = dict(binding, status='succeeded', run_id=123, service_unchanged=True,
                       cases=[{'name':'memory','passed':True},{'name':'timeout','passed':True}])

    def decision(self, **kw):
        return decide_build(self.goal, publication=self.pub, software=self.sw, kernel=self.kr, attempt=kw.pop('attempt',1), **kw)

    def test_all_measured_gates_only_mean_ready_for_review(self):
        result=self.decision(); self.assertEqual(result['state'],'ready_for_review')
        for k in ('automatic_retry','merge_authorized','deployment_authorized','qualification','promotion_authority'):
            self.assertIs(result[k],False)

    def test_reported_push_without_readback_is_rejected(self):
        self.pub['readback_complete']=False; self.assertIn('publication:unconfirmed',self.decision()['reasons'])

    def test_wrong_branch_head_rejected(self):
        self.pub['branch_head']='c'*40; self.assertEqual(self.decision()['state'],'repair_required')

    def test_manifest_mismatch_rejected_for_each_role(self):
        for name in ('pub','sw','kr'):
            with self.subTest(role=name):
                original=getattr(self,name)['source_map_sha256'];getattr(self,name)['source_map_sha256']='f'*64
                self.assertEqual(self.decision()['state'],'repair_required');getattr(self,name)['source_map_sha256']=original

    def test_failed_kernel_cannot_hide_behind_passing_software(self):
        self.kr['cases'][0]['passed']=False; self.assertEqual(self.decision()['state'],'repair_required')

    def test_empty_or_duplicate_kernel_cases_rejected(self):
        for cases in ([],[self.kr['cases'][0]]*2):
            self.kr['cases']=cases;self.assertEqual(self.decision()['state'],'repair_required')

    def test_boolean_counts_are_not_integers(self):
        for name in ('tests','failures','errors','skipped'):
            old=self.sw[name];self.sw[name]=False
            self.assertEqual(self.decision()['state'],'repair_required');self.sw[name]=old

    def test_truthy_booleans_rejected(self):
        for obj,key in ((self.pub,'readback_complete'),(self.sw,'passed'),(self.kr,'service_unchanged')):
            old=obj[key];obj[key]=1;self.assertEqual(self.decision()['state'],'repair_required');obj[key]=old

    def test_run_id_from_other_run_rejected(self):
        self.kr['run_id']=124;self.assertIn('kernel:run_mismatch',self.decision()['reasons'])

    def test_missing_run_cannot_be_inferred_from_test_count(self):
        self.sw.pop('run_id');self.assertEqual(self.decision()['state'],'repair_required')

    def test_skipped_and_wrong_test_counts_rejected(self):
        self.sw['skipped']=1;self.assertEqual(self.decision()['state'],'repair_required')
        self.sw['skipped']=0;self.sw['tests']=280;self.assertEqual(self.decision()['state'],'repair_required')

    def test_budget_exhaustion_stops(self):
        self.sw['passed']=False;self.assertEqual(self.decision(attempt=3)['state'],'budget_exhausted')

    def test_repeated_failure_stops_before_budget_ceiling(self):
        self.sw['passed']=False;old=self.decision()
        self.assertEqual(self.decision(attempt=2,previous_failure_sha256=old['failure_sha256'])['state'],'stalled')

    def test_invalid_attempts_rejected(self):
        for n in (True,0,4,1.0):
            with self.subTest(n=n),self.assertRaises(ValueError):self.decision(attempt=n)

    def test_goal_cannot_use_mutable_source_or_truthy_count(self):
        for goal in (replace(self.goal,source_commit='main'),replace(self.goal,max_attempts=True),replace(self.goal,kernel_cases=0)):
            with self.assertRaises(ValueError):goal.validate()

    def test_no_mutation_of_evidence(self):
        before=deepcopy((self.pub,self.sw,self.kr));self.decision()
        self.assertEqual(before,(self.pub,self.sw,self.kr))

    def test_authority_claim_cannot_be_promoted(self):
        self.kr['promotion_authority']=True;self.assertIn('kernel:authority_mismatch',self.decision()['reasons'])

    def store(self,registry):
        registry.register_project('test','Synthetic build gate')
        refs={}
        for role,body in (('publication',self.pub),('software',self.sw),('kernel',self.kr)):
            path='evidence/'+role+'.json';registry.put_artifact('test',path,canonical(body).encode(),'application/json')
            refs[role]=registry.artifact_ref('test',path)
        return refs

    def test_record_and_restart_replay_use_same_artifact_ref(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry=MerlinRegistry(Path(tmp)/'registry');refs=self.store(registry)
            kwargs=dict(project_id='test',goal=self.goal,references=refs,authenticate=lambda *_:True)
            a=record_build_decision(registry,**kwargs);b=record_build_decision(MerlinRegistry(registry.root),**kwargs)
            self.assertEqual(a,b)
            self.assertEqual(len(registry.artifact_history('test',a['decision_ref']['logical_path'])),1)

    def test_hash_or_nonempty_authentication_does_not_grant_trust(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry=MerlinRegistry(Path(tmp)/'registry');refs=self.store(registry)
            for value in (False,1,{'verified':True}):
                with self.subTest(value=value),self.assertRaises(PermissionError):
                    record_build_decision(registry,project_id='test',goal=self.goal,references=refs,authenticate=lambda *_,v=value:v)

    def test_tampered_exact_reference_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry=MerlinRegistry(Path(tmp)/'registry');refs=self.store(registry);refs['kernel']['sha256']='f'*64
            with self.assertRaises((ValueError,RuntimeError)):
                record_build_decision(registry,project_id='test',goal=self.goal,references=refs,authenticate=lambda *_:True)


if __name__=='__main__': unittest.main()
