"""Public frozen fixtures and independent original-byte citation oracles."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from merlin.learning_evidence import LearningEvidenceService
from merlin.learning_evidence_eval import (FIXTURE_SHA256, _setup_demo, evaluate_evidence_reader,
    grade_evidence_response, load_frozen_fixture, run_synthetic_evidence_demo)
from merlin.learning_platform import Actor, LearningConflictError, LearningPermissionError, LearningPlatform
from merlin.learning_titan_course import LAB_LESSON_ID
from merlin.project_registry import MerlinRegistry

COMMIT='b'*40  # Synthetic revision, not a claim about an actual repository commit.


class LearningEvidenceEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.fixture,self.platform,self.registry,self.context,self.service,self.teacher,
            self.learner,self.scope,self.pins,self.frozen)=_setup_demo(self.root,COMMIT)

    def retrieve(self,case_id,**extra):
        case=next(x for x in self.fixture['cases'] if x['case_id']==case_id)
        return self.service.retrieve(self.learner,**self.scope,query=case['query'],**extra)

    def grade(self,case_id,response):
        return grade_evidence_response(case_id,response,pinned_sources=self.pins,
            expected_binding={'tenant_id':self.learner.tenant_id,'project_id':'synthetic-learning-evidence',**self.scope},
            expected_source_manifest_ref=self.frozen['source_manifest_ref'])

    def test_fixture_bytes_partition_and_independent_utf8_oracles_are_frozen(self):
        path=Path(__file__).parent/'fixtures/learning-evidence-eval-v1.json'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),FIXTURE_SHA256)
        self.assertFalse(set(self.fixture['development_case_ids']) & set(self.fixture['evaluation_case_ids']))
        source=self.fixture['sources'][0];raw=source['content'].encode()
        self.assertGreater(len(raw),len(source['content']))  # em dash is multibyte
        self.assertEqual(source['expected_span']['end_byte'],len(raw))
        self.assertEqual(hashlib.sha256(raw).hexdigest(),source['source_sha256'])
        self.assertEqual(self.fixture['fixture_class'],'public_known_fixture')

    def test_real_reader_exact_sources_spans_abstention_and_conflict(self):
        for case in self.fixture['cases']:
            with self.subTest(case=case['case_id']):
                result=self.grade(case['case_id'],self.retrieve(case['case_id']))
                self.assertTrue(result['passed'],result['failures'])
        self.assertEqual(self.retrieve('eval-no-evidence')['citations'],[])
        self.assertEqual(self.retrieve('eval-declared-naming-conflict')['status'],'requires_review')

    def test_forged_text_plus_self_consistent_digest_fails_original_byte_grader(self):
        case='dev-placeholder-boundary';forged=deepcopy(self.retrieve(case))
        forged['citations'][0]['text']='Invented security assertion.'
        forged['citations'][0]['excerpt_sha256']=hashlib.sha256(forged['citations'][0]['text'].encode()).hexdigest()
        graded=self.grade(case,forged)
        self.assertFalse(graded['passed'])
        self.assertIn('citation_0_bytes_differ_from_original',graded['failures'])

    def test_forged_ref_span_missing_conflict_and_false_abstain_fail(self):
        case='dev-placeholder-boundary';valid=self.retrieve(case)
        variants=[]
        wrong=deepcopy(valid);wrong['citations'][0]['source_ref']['version']=2;variants.append(wrong)
        wrong=deepcopy(valid);wrong['citations'][0]['end_byte']-=2;variants.append(wrong)
        wrong=deepcopy(valid);wrong['status']='abstain';variants.append(wrong)
        wrong=deepcopy(valid);wrong['qualification']=True;variants.append(wrong)
        wrong=deepcopy(valid);wrong['query']='different frozen question';variants.append(wrong)
        for wrong in variants:self.assertFalse(self.grade(case,wrong)['passed'])
        conflict=self.retrieve('eval-declared-naming-conflict');conflict['conflicts']=[]
        self.assertFalse(self.grade('eval-declared-naming-conflict',conflict)['passed'])
        abstain=self.retrieve('eval-no-evidence');abstain['generated_answer']='A guess without evidence.'
        self.assertFalse(self.grade('eval-no-evidence',abstain)['passed'])

    def test_copied_valid_citations_with_wrong_or_missing_host_scope_fail(self):
        case='dev-placeholder-boundary';valid=self.retrieve(case)
        for field,value in [('tenant_id','wrong-tenant'),('project_id','wrong-project'),
                ('course_id','wrong-course'),('course_version',2),('manifest_sha256','0'*64)]:
            wrong=deepcopy(valid);wrong['binding'][field]=value
            with self.subTest(field=field):
                self.assertIn('wrong_or_missing_course_binding',self.grade(case,wrong)['failures'])
        for field in ('binding','source_manifest_ref'):
            wrong=deepcopy(valid);wrong.pop(field)
            with self.subTest(missing=field):self.assertFalse(self.grade(case,wrong)['passed'])
        wrong=deepcopy(valid);wrong['source_manifest_ref']['sha256']='0'*64
        self.assertIn('wrong_or_missing_source_manifest_reference',self.grade(case,wrong)['failures'])
        wrong=deepcopy(valid);wrong['source_manifest_ref']['version']=2
        self.assertFalse(self.grade(case,wrong)['passed'])

    def test_boolean_or_float_versions_cannot_impersonate_integer_identities(self):
        case='dev-placeholder-boundary';valid=self.retrieve(case)
        for value in (True,1.0):
            variants=[]
            wrong=deepcopy(valid);wrong['binding']['course_version']=value;variants.append(wrong)
            wrong=deepcopy(valid);wrong['source_manifest_ref']['version']=value;variants.append(wrong)
            for key in ('source_ref','record_ref'):
                wrong=deepcopy(valid);wrong['citations'][0][key]['version']=value;variants.append(wrong)
            for index,wrong in enumerate(variants):
                with self.subTest(value=value,index=index):self.assertFalse(self.grade(case,wrong)['passed'])

    def test_historical_pins_replay_after_latest_source_replacement_and_reload(self):
        before=self.retrieve('dev-placeholder-boundary');source=self.fixture['sources'][0]
        changed=self.context.ingest(namespace=source['namespace'],source_id=source['source_id'],title=source['title'],
            content=b'Later replacement intentionally lacks the old lexical evidence.\n',source_url=source['source_url'],
            source_version='synthetic-evidence-v2',epistemic=source['epistemic'],captured_at='2026-11-18T01:00:00Z')
        self.assertEqual(changed['source_ref']['version'],2)
        self.service=LearningEvidenceService(LearningPlatform(self.root/'learning.sqlite3'),MerlinRegistry(self.root/'registry'),
            tenant_projects={self.learner.tenant_id:'synthetic-learning-evidence'},namespaces=('merlin',))
        after=self.retrieve('dev-placeholder-boundary')
        self.assertEqual(after,before)
        self.assertTrue(self.grade('dev-placeholder-boundary',after)['passed'])
        self.assertEqual(after['citations'][0]['source_ref']['version'],1)

    def test_course_tenant_learner_and_lesson_boundaries(self):
        for actor in (Actor('unprovisioned-college',self.learner.actor_id,'learner'),
                      Actor(self.learner.tenant_id,'unenrolled-learner','learner'),self.teacher):
            with self.subTest(actor=actor),self.assertRaises((LearningPermissionError,KeyError)):
                self.service.retrieve(actor,**self.scope,query='placeholder')
        wrong={**self.scope,'manifest_sha256':'0'*64}
        with self.assertRaises((ValueError,LearningConflictError)):
            self.service.retrieve(self.learner,**wrong,query='placeholder')
        restricted=self.retrieve('eval-review-policy',lesson_id=LAB_LESSON_ID)
        self.assertEqual(restricted['status'],'abstain');self.assertEqual(restricted['citations'],[])

    def test_demo_replay_persists_protocol_candidates_report_and_no_scores(self):
        first=run_synthetic_evidence_demo(self.root,COMMIT);second=run_synthetic_evidence_demo(self.root,COMMIT)
        self.assertEqual(first,second)
        self.assertEqual(first['metrics'],{'case_count':4,'passed':4,'failed':0,'development_passed':1,'evaluation_passed':3})
        report=json.loads(self.registry.read_artifact_ref(first['report_ref'])['content'])
        protocol=json.loads(self.registry.read_artifact_ref(first['protocol_ref'])['content'])
        self.assertEqual(protocol['fixture_sha256'],FIXTURE_SHA256)
        for case in report['cases']:
            candidate=json.loads(self.registry.read_artifact_ref(case['candidate_ref'])['content'])
            self.assertTrue(self.grade(case['case_id'],candidate)['passed'])
            self.assertEqual(case['candidate_ref']['version'],1)
        self.assertFalse(report['mastery_updated']);self.assertFalse(report['qualification'])
        with self.platform._connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM learning_submissions').fetchone()[0],0)
            tables={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'learner_attempts' in tables:self.assertEqual(db.execute('SELECT COUNT(*) FROM learner_attempts').fetchone()[0],0)

    def test_scoped_candidate_failures_are_preserved_without_weakening_oracles(self):
        result=evaluate_evidence_reader(self.service,self.registry,self.learner,course_scope=self.scope,pinned_sources=self.pins,
            source_manifest_ref=self.frozen['source_manifest_ref'],source_commit=COMMIT,lesson_id=LAB_LESSON_ID)
        self.assertGreater(result['metrics']['failed'],0)
        report=json.loads(self.registry.read_artifact_ref(result['report_ref'])['content'])
        failed=[x for x in report['cases'] if not x['passed']]
        self.assertTrue(failed)
        for case in failed:
            self.assertTrue(case['failures'])
            self.assertTrue(self.registry.read_artifact_ref(case['candidate_ref'])['content'])
        full=run_synthetic_evidence_demo(self.root,COMMIT)
        self.assertNotEqual(result['report_ref']['logical_path'],full['report_ref']['logical_path'])
        self.assertTrue(self.registry.read_artifact_ref(result['report_ref'])['content'])


if __name__=='__main__':unittest.main()
