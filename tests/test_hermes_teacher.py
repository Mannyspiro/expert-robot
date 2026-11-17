"""Local teacher contracts with real worker/outbox/journal; no live model or CACE."""
from contextlib import closing
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from merlin.artifact_ref import ArtifactRef
from merlin.event_outbox import MerlinEventOutbox, OutboxConflict
from merlin.hermes_stage_journal import HermesStageJournal, StageJournalConflict
from merlin.hermes_worker import HermesWorker, HERMES_TASK_TOPIC, HERMES_TEACHER_TASK_TOPIC
from merlin.hermes_teacher import build_teacher_review_handler, enqueue_teacher_task


def work_task(refs, task_id="review-1", partition="development"):
    return {
        "schema": "merlin-research-task/2", "task_id": task_id,
        "hypothesis_id": "hypothesis-1", "stage": "teacher_review", "objective": "Review exact work",
        "approval_ref": "test-approval", "lease_ref": "test-lease",
        "resource_budget": {"cpu_cores": 1, "memory_bytes": 8 * 1024 * 1024,
                            "max_wall_seconds": 20, "compute_budget_units": 1},
        "artifact_refs": refs, "authority": "bounded_execution_only", "promotion_authority": False,
        "experiment_spec": {"work_id": "work-1", "repository": "Mannyspiro/expert-robot",
            "source_commit": "a" * 40, "author_ids": ["hermes-coder"],
            "reviewer_id": "hermes-teacher", "partition": partition,
            "artifacts": [{"artifact_ref": ref, "kind": "source", "schema": "text/plain",
                           "tool_identity": "fixture@1"} for ref in refs],
            "acceptance_criteria": {"correctness": "Retain exact behavior", "regression": "Add a negative control"}},
    }


def good_review(request):
    return {
        "assignment_sha256": request["assignment_sha256"],
        "artifact_reviews": [{"index": i, "disposition": "reviewed", "rationale": "Inspected fixture bytes",
            "citations": [{"start": 0, "end": len(text.encode('utf-8')), "quote": text}]}
            for i, text in enumerate(request["artifact_texts"])],
        "criterion_reviews": [{"criterion_id": key, "disposition": "addressed",
            "rationale": "Review assertion, not a test receipt", "artifact_indexes": [0]}
            for key in request["assignment"]["acceptance_criteria"]],
        "lessons": [{"rule": "Keep a negative control", "applicability": "Behavior-preserving repair",
                     "counterexample": "A test of unrelated code is insufficient",
                     "regression_test": "Replay the minimal failing input", "artifact_indexes": [0]}],
        "limitations": ["Fixture reviewer; this does not prove behavior or independent verification"],
    }


class TeacherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.out = MerlinEventOutbox(self.root / "outbox.sqlite3")
        self.journal = HermesStageJournal(self.root / "hermes-stage-journal.sqlite3")
        self.contents = [b"def identity(x): return x\n", b"assert identity(1) == 1\n"]
        self.refs = [ArtifactRef("merlin", "fixture/"+str(i)+".py", 1, hashlib.sha256(b).hexdigest()).to_dict()
                     for i,b in enumerate(self.contents)]
        self.task = work_task(self.refs)
        self.calls = []
        self.modify = lambda r: r
        self.admission = lambda t,c: True
        self.handler = self.make_handler()

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, ref):
        return self.contents[self.refs.index(ref)]

    def provider(self, request):
        self.calls.append(deepcopy(request))
        return self.modify(good_review(request))

    def make_handler(self, **changes):
        args = dict(journal=self.journal, read_artifact=self.read, reviewer=self.provider,
                    reviewer_id="hermes-teacher", reviewer_build_sha256="1"*64,
                    admission_validator=lambda t,c:self.admission(t,c))
        args.update(changes)
        return build_teacher_review_handler(**args)

    def context(self, task=None):
        t = self.task if task is None else task
        return SimpleNamespace(**{k:deepcopy(t[k]) for k in ("task_id", "hypothesis_id", "approval_ref", "lease_ref", "resource_budget")},
            artifact_refs=tuple(deepcopy(t["artifact_refs"])), idempotency_key="hermes-teacher-task-handler:"+t["task_id"],
            check_cancelled=lambda:None)

    def execute(self, task=None, handler=None):
        t = self.task if task is None else task
        return (handler or self.handler)(t,self.context(t))

    def worker(self, **changes):
        args=dict(handlers={"teacher_review":self.handler}, task_topic=HERMES_TEACHER_TASK_TOPIC,
                  worker_id="teacher-worker", approval_validator=lambda *a:True,
                  lease_validator=lambda *a:True, artifact_ref_validator=lambda r:r in self.refs,
                  retry_delay_seconds=0)
        args.update(changes)
        return HermesWorker(self.out,**args)

    def enqueue(self, task=None):
        return enqueue_teacher_task(self.out, self.task if task is None else task,
                                    reviewer_id="hermes-teacher", admission_validator=lambda t:True)

    def test_real_worker_completes_teacher_task_and_keeps_verification_separate(self):
        event=self.enqueue()
        response=self.worker().run_once()
        self.assertEqual(response['status'],'completed')
        result=response['receipt']['result']
        self.assertEqual(result['disposition'],'ready_for_independent_verification')
        self.assertEqual(result['verification_status'],'not_requested')
        self.assertIs(result['qualification'],False)
        self.assertIs(result['promotion_authority'],False)
        self.assertEqual(response['receipt']['evidence_refs'],[])
        self.assertEqual(self.out.get(event['event_id'])['state'],'acknowledged')

    def test_coder_cannot_claim_teacher_work(self):
        event=self.enqueue()
        coder=HermesWorker(self.out,handlers={'research':lambda t,c:{}},
                           approval_validator=lambda *a:True,lease_validator=lambda *a:True)
        self.assertIsNone(coder.run_once())
        self.assertEqual(self.out.get(event['event_id'])['attempts'],0)
        self.assertEqual(self.worker().run_once()['status'],'completed')

    def test_teacher_cannot_claim_coder_work(self):
        task=deepcopy(self.task);task['stage']='research'
        event=self.out.enqueue('coder-task',HERMES_TASK_TOPIC,task)
        self.assertIsNone(self.worker().run_once())
        self.assertEqual(self.out.get(event['event_id'])['attempts'],0)

    def test_lane_configuration_cannot_register_other_execution_stages(self):
        for change in [dict(task_topic='merlin.cace.verify'),dict(task_topic=HERMES_TASK_TOPIC),
                       dict(handlers={'research':lambda t,c:{}}),dict(task_topic=[])]:
            with self.subTest(change=change),self.assertRaises(ValueError): self.worker(**change)

    def test_telemetry_identifies_teacher_without_impersonating_cace(self):
        self.enqueue(); self.worker().run_once()
        with closing(self.out._connect()) as db:
            events=[json.loads(r[0]) for r in db.execute("SELECT payload_json FROM event_outbox WHERE topic LIKE 'merlin.telemetry.%'")]
        self.assertTrue(events)
        self.assertTrue(all(e['source']=='hermes' for e in events))
        self.assertTrue(all(e['payload']['agent_id']=='hermes-teacher' for e in events))

    def test_lessons_target_both_coders_but_are_never_automatically_adopted(self):
        result=self.execute()
        lesson=result['shared_lesson_proposals'][0]
        self.assertEqual(lesson['audience'],['hermes-coder','hermes-teacher'])
        self.assertIs(lesson['automatic_adoption'],False)
        self.assertEqual(lesson['state'],'proposal_requires_evaluation')

    def test_shared_lesson_is_source_bound_and_content_addressed(self):
        lesson=self.execute()['shared_lesson_proposals'][0]
        body={k:v for k,v in lesson.items() if k!='lesson_id'}
        digest=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
        self.assertEqual(lesson['lesson_id'],digest)
        self.assertEqual(lesson['source_artifact_refs'],self.refs[:1])
        self.assertEqual(lesson['source_commit'],'a'*40)

    def test_verification_handoff_covers_inventory_and_excludes_both_coders(self):
        handoff=self.execute()['verification_handoff']
        self.assertEqual(handoff['state'],'not_dispatched')
        self.assertEqual(handoff['subject_artifact_refs'],self.refs)
        self.assertEqual(handoff['excluded_verifier_ids'],['hermes-coder','hermes-teacher'])
        self.assertIs(handoff['requires_independent_policy'],True)

    def test_self_review_is_rejected_before_provider(self):
        self.task['experiment_spec']['author_ids'].append('hermes-teacher')
        with self.assertRaises(PermissionError):self.execute()
        self.assertEqual(self.calls,[])

    def test_assignment_to_different_reviewer_is_rejected(self):
        self.task['experiment_spec']['reviewer_id']='other-teacher'
        with self.assertRaises(PermissionError): self.execute()
        self.assertEqual(self.calls,[])

    def test_missing_or_duplicate_artifact_review_is_rejected(self):
        for kind in ['missing','duplicate']:
            def change(r):
                r['artifact_reviews']=r['artifact_reviews'][:1] if kind=='missing' else [r['artifact_reviews'][0]]*2
                return r
            self.modify=change
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.execute()

    def test_missing_or_duplicate_criterion_is_rejected(self):
        for kind in ['missing','duplicate']:
            def change(r):
                r['criterion_reviews']=r['criterion_reviews'][:1] if kind=='missing' else [r['criterion_reviews'][0]]*2
                return r
            self.modify=change
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.execute()

    def test_empty_or_mismatched_manifest_is_rejected(self):
        for refs in [[],self.refs[:1],self.refs[::-1]]:
            t=deepcopy(self.task);t['artifact_refs']=refs
            with self.subTest(refs=refs),self.assertRaises(ValueError):self.execute(t)
        self.assertEqual(self.calls,[])

    def test_false_quotation_is_rejected(self):
        def change(r):r['artifact_reviews'][0]['citations'][0]['quote']='invented';return r
        self.modify=change
        with self.assertRaisesRegex(ValueError,'quotation'):self.execute()

    def test_bad_and_boolean_byte_ranges_are_rejected(self):
        for start,end in [(True,3),(-1,3),(0,9999),(1,1)]:
            def change(r):r['artifact_reviews'][0]['citations'][0].update(start=start,end=end);return r
            self.modify=change
            with self.subTest(start=start,end=end),self.assertRaises(ValueError):self.execute()

    def test_assessed_artifact_requires_citation(self):
        def change(r):r['artifact_reviews'][0]['citations']=[];return r
        self.modify=change
        with self.assertRaises(ValueError):self.execute()

    def test_unassessed_work_is_explicitly_incomplete(self):
        def change(r):r['artifact_reviews'][0].update(disposition='not_assessed',citations=[]);return r
        self.modify=change
        self.assertEqual(self.execute()['disposition'],'review_incomplete')

    def test_gaps_request_changes_not_verification(self):
        def change(r):r['criterion_reviews'][0]['disposition']='gap';return r
        self.modify=change
        self.assertEqual(self.execute()['disposition'],'changes_requested')

    def test_model_cannot_supply_verifier_identity_or_promotion(self):
        for field in ['verification_status','promotion_authority','reviewer_id','signed_attestation']:
            self.modify=lambda r:{**r,field:True}
            with self.subTest(field=field),self.assertRaises(ValueError):self.execute()

    def test_model_cannot_label_artifact_verified(self):
        def change(r):r['artifact_reviews'][0]['disposition']='verified';return r
        self.modify=change
        with self.assertRaises(ValueError):self.execute()

    def test_reply_to_different_assignment_is_rejected(self):
        self.modify=lambda r:{**r,'assignment_sha256':'b'*64}
        with self.assertRaises(ValueError):self.execute()

    def test_heldout_cannot_emit_shared_lessons(self):
        self.task['experiment_spec']['partition']='heldout'
        with self.assertRaises(PermissionError):self.execute()

    def test_heldout_can_be_reviewed_without_training_transfer(self):
        self.task['experiment_spec']['partition']='heldout'
        self.modify=lambda r:{**r,'lessons':[]}
        self.assertEqual(self.execute()['shared_lesson_proposals'],[])

    def test_lesson_requires_counterexample_and_regression(self):
        for key in ['applicability','counterexample','regression_test']:
            def change(r):del r['lessons'][0][key];return r
            self.modify=change
            with self.subTest(key=key),self.assertRaises(ValueError):self.execute()

    def test_missing_limitations_is_rejected(self):
        self.modify=lambda r:{**r,'limitations':[]}
        with self.assertRaises(ValueError):self.execute()

    def test_completed_replay_does_not_call_provider_again(self):
        result=self.execute()
        restarted=self.make_handler(journal=HermesStageJournal(self.journal.path))
        self.assertEqual(self.execute(handler=restarted),result)
        self.assertEqual(len(self.calls),1)

    def test_changed_commit_criteria_and_partition_rejected_on_replay(self):
        self.execute()
        for key,value in [('source_commit','b'*40),('acceptance_criteria',{'new':'moved goalposts'}),('partition','heldout')]:
            t=deepcopy(self.task);t['experiment_spec'][key]=value
            with self.subTest(key=key),self.assertRaises(StageJournalConflict):self.execute(t)
        self.assertEqual(len(self.calls),1)

    def test_changed_teacher_build_rejected_on_replay(self):
        self.execute()
        with self.assertRaises(StageJournalConflict):
            self.execute(handler=self.make_handler(reviewer_build_sha256='2'*64))

    def test_changed_bytes_rejected_even_during_completed_replay(self):
        self.execute();self.contents[0]=b'changed'
        with self.assertRaisesRegex(ValueError,'digest'):self.execute()
        self.assertEqual(len(self.calls),1)

    def test_mutated_durable_result_rejected(self):
        self.execute()
        with closing(self.journal._connect()) as db,db:
            db.execute("UPDATE hermes_stage_runs SET result_json='{}'")
        with self.assertRaises(StageJournalConflict):self.execute()

    def test_missing_completed_checkpoint_is_not_regenerated(self):
        self.execute()
        with closing(self.journal._connect()) as db,db:
            db.execute("UPDATE hermes_stage_runs SET candidate_set_json=NULL")
        with self.assertRaises(StageJournalConflict):self.execute()
        self.assertEqual(len(self.calls),1)

    def test_generated_checkpoint_recovers_after_completion_failure(self):
        with patch.object(self.journal,'complete',side_effect=OSError('fixture')):
            with self.assertRaises(OSError):self.execute()
        self.execute()
        self.assertEqual(len(self.calls),1)

    def test_provider_mutation_cannot_change_bound_assignment(self):
        def provider(request):
            r=good_review(request)
            request['assignment']['source_commit']='b'*40
            return r
        result=self.execute(handler=self.make_handler(reviewer=provider))
        self.assertEqual(result['source_commit'],'a'*40)

    def test_admission_denied_or_truthy_nonboolean_blocks_provider(self):
        for value in [False,'yes',1]:
            self.admission=lambda t,c:value
            with self.subTest(value=value),self.assertRaises(PermissionError):self.execute()
        self.assertEqual(self.calls,[])

    def test_final_admission_revocation_blocks_completion(self):
        values=iter([True,False]);self.admission=lambda t,c:next(values)
        with self.assertRaises(PermissionError):self.execute()
        with closing(self.journal._connect()) as db:
            self.assertEqual(db.execute('SELECT state FROM hermes_stage_runs').fetchone()[0],'generated')

    def test_context_identity_and_lane_must_match(self):
        for field,value in [('task_id','wrong'),('approval_ref','wrong'),('lease_ref','wrong'),
                            ('idempotency_key','hermes-task-handler:review-1')]:
            c=self.context();setattr(c,field,value)
            with self.subTest(field=field),self.assertRaises(PermissionError):self.handler(self.task,c)
        self.assertEqual(self.calls,[])

    def test_budget_limits_input_and_output(self):
        t=deepcopy(self.task);t['resource_budget']['memory_bytes']=8
        with self.assertRaisesRegex(ValueError,'admission'):self.execute(t)
        self.modify=lambda r:{**r,'limitations':['x'*300000]}
        with self.assertRaisesRegex(ValueError,'byte limit'):self.execute()

    def test_non_utf8_requires_dedicated_adapter_not_false_review(self):
        raw=b'\xff';ref=ArtifactRef('merlin','binary.bin',1,hashlib.sha256(raw).hexdigest()).to_dict()
        t=work_task([ref])
        with self.assertRaises(UnicodeDecodeError): self.execute(t,self.make_handler(read_artifact=lambda r:raw))
        self.assertEqual(self.calls,[])

    def test_ack_failure_retries_without_another_teacher_call(self):
        event=self.enqueue();worker=self.worker()
        with patch.object(self.out,'acknowledge_with_events',side_effect=OSError('fixture')):
            self.assertEqual(worker.run_once()['status'],'pending')
        self.assertEqual(worker.run_once()['status'],'completed')
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.out.get(event['event_id'])['state'],'acknowledged')

    def test_cancellation_during_review_never_announces_completion(self):
        event=self.enqueue()
        def provider(request):
            self.out.cancel(event['event_id'],'test-operator')
            return good_review(request)
        self.handler=self.make_handler(reviewer=provider)
        self.assertEqual(self.worker().run_once()['status'],'cancelled')
        with closing(self.out._connect()) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM event_outbox WHERE topic='merlin.telemetry.task.completed'").fetchone()[0],0)

    def test_publication_is_idempotent_and_rejects_changed_task(self):
        self.assertEqual(self.enqueue()['event_id'],self.enqueue()['event_id'])
        t=deepcopy(self.task);t['objective']='changed'
        with self.assertRaises(OutboxConflict):self.enqueue(t)

    def test_publisher_requires_real_boolean_admission(self):
        with self.assertRaises(PermissionError):enqueue_teacher_task(self.out,self.task,
            reviewer_id='hermes-teacher',admission_validator=lambda t:'yes')
        self.assertEqual(self.out.counts()['pending'],0)

    def test_no_provider_or_verifier_is_installed_by_this_module(self):
        result=self.execute()
        self.assertEqual(result['verification_authority'],'independent_cace_only')
        self.assertIn('deductive',self.calls[0]['scientific_loop_contract']['reasoning_modes'])
        self.assertEqual(self.calls[0]['resource_budget'],self.task['resource_budget'])
        self.assertEqual(result['artifact_refs'],[])
        self.assertEqual(result['review_scope'],'supplied_text_artifact_inventory_only')

    def test_teacher_catalog_names_discoverable_guards(self):
        root=Path(__file__).resolve().parents[1]
        rows=json.loads((root/'config/known_failure_classes.json').read_text())['classes']
        row=next(r for r in rows if r['id']=='hermes-cross-role-task-claim')
        self.assertEqual(row['guard'],'tests/test_hermes_teacher.py')
        names=set(unittest.defaultTestLoader.getTestCaseNames(TeacherTests))
        for ref in row['regressions']:
            owner,method=ref.split('.')
            self.assertEqual(owner,'TeacherTests')
            self.assertIn(method,names)

    def test_gate_includes_teacher_suite(self):
        text=(Path(__file__).resolve().parents[1]/'scripts/merlin_research_stack_gate.py').read_text()
        self.assertIn('"test_hermes_teacher.py"',text)


if __name__ == '__main__':
    unittest.main()
