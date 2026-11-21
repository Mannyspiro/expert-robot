"""Build stopping contracts; synthetic host authentication, real canonical store."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from merlin.build_loop import BuildGoal, decide_build, record_build_decision, software_inventory_digest
from merlin.branch_research import canonical
from merlin.project_registry import MerlinRegistry


class BuildLoopTests(unittest.TestCase):
    def setUp(self):
        self.inventory = tuple('fixture.Tests.test_case_%03d' % n for n in range(281))
        self.goal = BuildGoal('a'*40, 'b'*64, 281, 2,
            software_test_inventory_sha256=software_inventory_digest(self.inventory),
            required_kernel_cases=('memory', 'timeout'))
        binding = dict(source_commit=self.goal.source_commit, source_map_sha256=self.goal.source_map_sha256,
                       qualification=False, promotion_authority=False)
        self.pub = dict(binding, status='observed', branch_head=self.goal.source_commit, readback_complete=True)
        self.sw = dict(binding, status='succeeded', tests=281, failures=0, errors=0, skipped=0,
            passed=True, run_id=123, test_inventory_sha256=self.goal.software_test_inventory_sha256)
        self.kr = dict(binding, status='succeeded', run_id=123, service_unchanged=True,
                       cases=[{'name':'memory','passed':True},{'name':'timeout','passed':True}])

    def decision(self, **kw):
        return decide_build(self.goal, publication=self.pub, software=self.sw, kernel=self.kr, attempt=kw.pop('attempt',1), **kw)

    def test_all_measured_gates_only_mean_ready_for_review(self):
        result=self.decision(); self.assertEqual(result['state'],'ready_for_review')
        self.assertEqual(result['schema'], 'merlin-build-loop-decision/2')
        self.assertEqual(result['acceptance']['required_kernel_cases'], ['memory', 'timeout'])
        self.assertEqual(result['acceptance']['software_test_inventory_sha256'], self.goal.software_test_inventory_sha256)
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

    def test_different_passing_kernel_checks_cannot_replace_required_checks(self):
        # Regression: the v1 gate accepted any distinct names with the right count.
        self.kr['cases'] = [{'name': 'unrelated-file-inventory', 'passed': True},
                            {'name': 'unrelated-json-parse', 'passed': True}]
        result = self.decision()
        self.assertEqual(result['state'], 'repair_required')
        self.assertIn('kernel:case_inventory_mismatch', result['reasons'])

    def test_missing_required_case_and_unexpected_case_are_rejected(self):
        for cases in ([self.kr['cases'][0]], self.kr['cases'] + [{'name': 'other', 'passed': True}]):
            with self.subTest(cases=cases):
                self.kr['cases'] = cases
                self.assertIn('kernel:case_inventory_mismatch', self.decision()['reasons'])

    def test_required_case_order_is_not_meaningful(self):
        first = self.decision()
        self.kr['cases'].reverse()
        self.goal = replace(self.goal, required_kernel_cases=tuple(reversed(self.goal.required_kernel_cases)))
        self.assertEqual(first, self.decision())

    def test_wrong_or_missing_executed_software_inventory_fails_closed(self):
        for value in (None, 'f'*64, 'latest', True):
            with self.subTest(value=value):
                self.sw['test_inventory_sha256'] = value
                result = self.decision()
                self.assertEqual(result['state'], 'repair_required')
                self.assertIn('software:test_inventory_mismatch', result['reasons'])

    def test_same_count_different_software_tests_are_not_the_same_inventory(self):
        changed = list(self.inventory)
        changed[-1] = 'fixture.Tests.unrelated_test'
        self.sw['test_inventory_sha256'] = software_inventory_digest(changed)
        self.assertEqual(self.sw['tests'], self.goal.software_tests)
        self.assertIn('software:test_inventory_mismatch', self.decision()['reasons'])

    def test_executed_inventory_digest_is_order_independent(self):
        self.assertEqual(software_inventory_digest(self.inventory),
                         software_inventory_digest(tuple(reversed(self.inventory))))

    def test_executed_inventory_rejects_empty_duplicate_or_invalid_ids(self):
        for ids in ([], ['a', 'a'], [''], ['a\nforged'], [' a'], [True], 'test-case'):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                software_inventory_digest(ids)

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

    def test_different_failed_kernel_case_is_not_an_identical_failure(self):
        # Regression: v1 hashed only kernel:acceptance_failed and falsely stalled.
        self.kr['cases'][0]['passed'] = False
        old = self.decision()
        self.kr['cases'][0]['passed'] = True
        self.kr['cases'][1]['passed'] = False
        current = self.decision(attempt=2, previous_failure_sha256=old['failure_sha256'])
        self.assertEqual(current['state'], 'repair_required')
        self.assertNotEqual(old['failure_sha256'], current['failure_sha256'])

    def test_same_failed_kernel_case_stalls_across_new_run_and_timestamps(self):
        self.kr['cases'][0]['passed'] = False
        old = self.decision()
        self.sw['run_id'] = self.kr['run_id'] = 999
        self.sw['timestamp'] = '2026-11-21T18:00:00Z'
        self.kr['elapsed_seconds'] = 3.75
        self.kr['cases'][0]['duration'] = 1.25
        self.kr['cases'].reverse()
        current = self.decision(attempt=2, previous_failure_sha256=old['failure_sha256'])
        self.assertEqual(current['state'], 'stalled')
        self.assertEqual(old['failure_sha256'], current['failure_sha256'])

    def test_different_failed_software_test_is_not_an_identical_failure(self):
        self.sw.update(passed=False, failures=1, failed_test_ids=[self.inventory[0]])
        old = self.decision()
        self.sw['failed_test_ids'] = [self.inventory[1]]
        current = self.decision(attempt=2, previous_failure_sha256=old['failure_sha256'])
        self.assertEqual(current['state'], 'repair_required')
        self.assertNotEqual(old['failure_sha256'], current['failure_sha256'])

    def test_same_software_failures_stall_independent_of_run_and_order(self):
        self.sw.update(passed=False, failures=2, failed_test_ids=list(self.inventory[:2]))
        old = self.decision()
        self.sw['run_id'] = self.kr['run_id'] = 124
        self.sw['failed_test_ids'].reverse()
        self.sw['timestamp'] = 'later'
        current = self.decision(attempt=2, previous_failure_sha256=old['failure_sha256'])
        self.assertEqual(current['state'], 'stalled')

    def test_incomplete_software_failure_identity_cannot_claim_repetition(self):
        self.sw.update(passed=False, failures=1)
        old = self.decision()
        self.assertIsNone(old['failure_sha256'])
        self.assertIs(old['failure_identity_complete'], False)
        self.assertEqual(self.decision(attempt=2, previous_failure_sha256='f'*64)['state'], 'repair_required')
        self.assertEqual(self.decision(attempt=3)['state'], 'budget_exhausted')

    def test_error_and_skipped_test_identity_are_distinct(self):
        for count_key, ids_key in (('errors', 'error_test_ids'), ('skipped', 'skipped_test_ids')):
            with self.subTest(count_key=count_key):
                self.setUp()
                self.sw.update({count_key: 1, ids_key: [self.inventory[0]], 'passed': False})
                old = self.decision()
                self.sw[ids_key] = [self.inventory[1]]
                self.assertNotEqual(old['failure_sha256'], self.decision()['failure_sha256'])

    def test_contradictory_failure_details_cannot_pass_or_fingerprint(self):
        self.sw['failed_test_ids'] = [self.inventory[0]]
        result = self.decision()
        self.assertEqual(result['state'], 'repair_required')
        self.assertIn('software:failure_details_mismatch', result['reasons'])
        self.assertIsNone(result['failure_sha256'])

    def test_failure_signature_binds_acceptance_criteria(self):
        self.kr['cases'][0]['passed'] = False
        old = self.decision()
        self.goal = replace(self.goal, required_kernel_cases=('memory', 'different'))
        self.kr['cases'][1]['name'] = 'different'
        current = self.decision(attempt=2, previous_failure_sha256=old['failure_sha256'])
        self.assertEqual(current['state'], 'repair_required')
        self.assertNotEqual(old['acceptance_sha256'], current['acceptance_sha256'])

    def test_invalid_attempts_rejected(self):
        for n in (True,0,4,1.0):
            with self.subTest(n=n),self.assertRaises(ValueError):self.decision(attempt=n)

    def test_goal_cannot_use_mutable_source_or_truthy_count(self):
        for goal in (replace(self.goal,source_commit='main'),replace(self.goal,max_attempts=True),replace(self.goal,kernel_cases=0)):
            with self.assertRaises(ValueError):goal.validate()

    def test_missing_or_mutable_acceptance_identity_is_rejected(self):
        cases = (replace(self.goal, software_test_inventory_sha256=None),
                 replace(self.goal, software_test_inventory_sha256='latest'),
                 replace(self.goal, required_kernel_cases=()),
                 replace(self.goal, required_kernel_cases=['memory', 'timeout']),
                 replace(self.goal, required_kernel_cases=('memory', 'memory')),
                 replace(self.goal, required_kernel_cases=('memory', ' timeout')),
                 BuildGoal('a'*40, 'b'*64, 281, 2))
        for goal in cases:
            with self.subTest(goal=goal), self.assertRaises(ValueError):
                decide_build(goal, publication=self.pub, software=self.sw, kernel=self.kr, attempt=1)

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
