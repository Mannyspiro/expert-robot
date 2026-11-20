"""Synthetic end-to-end course/lab/evidence persistence; no provider doubles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from merlin.hypothesis_ledger import HypothesisLedger
from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.learner_model import LearnerStore, learner_subject_id
from merlin.learning_lab_bridge import LearningLabBridge
from merlin.learning_platform import Actor, LearningConflictError, LearningPermissionError, LearningPlatform
from merlin.learning_titan_course import (LAB_LESSON_ID, LAB_TASK_ID, create_titan_course,
                                         run_synthetic_titan_demo, titan_course_manifest)
from merlin.project_registry import MerlinRegistry
from merlin.research_evidence import ResearchEvidenceRecorder

SOURCE = 'a' * 40  # Explicit synthetic revision, not a claim about a real commit.


class TitanLearningIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.teacher = Actor('synthetic-college', 'synthetic-teacher', 'instructor')
        self.reviewer = Actor('synthetic-college', 'synthetic-reviewer', 'reviewer')
        self.learner = Actor('synthetic-college', 'synthetic-learner', 'learner')
        self.platform = LearningPlatform(self.root/'learning.sqlite3')
        self.learners = LearnerStore(self.root/'learning.sqlite3')
        self.registry = MerlinRegistry(self.root/'registry')
        self.registry.register_project('titan-learning', 'Synthetic course research evidence')
        self.ledger = HypothesisLedger(self.root/'hypotheses.sqlite3')
        self.graph = MerlinKnowledgeGraph(self.root/'graph.sqlite3')
        self.recorder = ResearchEvidenceRecorder(self.registry,self.ledger,self.graph)
        self.bridge = self.make_bridge()

    def make_bridge(self,platform=None,recorder=None):
        return LearningLabBridge(platform or self.platform,recorder or self.recorder,
            tenant_projects={'synthetic-college':'titan-learning'},source_commit=SOURCE)

    def publish(self):
        course = create_titan_course(self.platform,self.teacher,SOURCE)
        self.platform.review_course(self.reviewer,course['course_id'],course['version'],'approved',
            'Synthetic test approval: source, rubric and structural-model limits checked.')
        self.course = self.platform.publish_course(self.teacher,course['course_id'])
        self.platform.enroll(self.learner,self.course['course_id'])
        return self.course

    def args(self,**changes):
        return {'course_id':self.course['course_id'],'course_version':self.course['version'],
            'manifest_sha256':self.course['manifest_sha256'],'lesson_id':LAB_LESSON_ID,'run_id':'known-fixture-run',**changes}

    def run_lab(self,actor=None,**changes):
        return self.bridge.run_titan_lab(actor or self.learner,**self.args(**changes),
            prediction='Prespecified known fixtures: valid structure accepts; missing context, custom suite, research contamination and unknown version reject. No crypto security prediction.')

    def submit(self,**changes):
        return self.bridge.submit_lab_assessment(self.learner,**self.args(**changes),submission_id='known-fixture-submission',
            reflection='This reproduces known structural fixtures. A wrong-tenant binding in authenticated data needs a separate implementation test; security and transfer understanding remain unassessed.')

    def test_curated_manifest_is_fresh_source_pinned_and_has_substantive_transfer(self):
        first=titan_course_manifest(SOURCE);second=titan_course_manifest(SOURCE)
        self.assertEqual(first,second)
        first['lessons'][0]['body']='changed fixture'
        self.assertNotEqual(first,second)
        self.assertEqual(len(second['objectives']),3)
        self.assertTrue(all(SOURCE in x['source_uri'] for x in second['resources']))
        self.assertTrue(all(x['human_review_required'] for x in second['assessments']))
        self.assertTrue(all(len(x['rubric'])==4 for x in second['assessments']))
        self.assertIn('new counterexample',second['lessons'][2]['exercise']['prompt'])
        self.assertFalse(second['research_scope']['cryptographic_operations_implemented'])
        self.assertFalse(second['research_scope']['educational_efficacy_established'])
        self.assertEqual(second['lessons'][1]['exercise']['task_id'],LAB_TASK_ID)
        for bad in ('main','A'*40,'a'*39):
            with self.assertRaises(ValueError):titan_course_manifest(bad)

    def test_draft_requires_separate_reviewer_before_publication_and_enrollment(self):
        course=create_titan_course(self.platform,self.teacher,SOURCE)
        self.assertEqual(course['status'],'draft')
        with self.assertRaises(LearningConflictError):self.platform.publish_course(self.teacher,course['course_id'])
        with self.assertRaises(LearningConflictError):self.platform.enroll(self.learner,course['course_id'])
        own_reviewer=Actor(self.teacher.tenant_id,self.teacher.actor_id,'reviewer')
        with self.assertRaises(LearningPermissionError):
            self.platform.review_course(own_reviewer,course['course_id'],1,'approved')

    def test_real_course_lab_submission_and_reload_preserve_exact_canonical_evidence(self):
        self.publish();receipt=self.run_lab();submitted=self.submit()
        ref=receipt['artifact_ref'];blob=self.registry.read_artifact_ref(ref,max_bytes=65536)
        report=json.loads(blob['content'])
        self.assertEqual(report['binding']['learner_id'],self.learner.actor_id)
        self.assertEqual(report['binding']['manifest_sha256'],self.course['manifest_sha256'])
        self.assertEqual(report['experiment_class'],'known_fixture_reproduction')
        self.assertFalse(report['cryptographic_operations_performed'])
        self.assertEqual(hashlib.sha256(blob['content']).hexdigest(),ref['sha256'])
        self.assertEqual(self.ledger.get(receipt['hypothesis_id']).status,'proposed')
        self.assertEqual(submitted['status'],'pending_review')
        self.assertFalse(submitted['mastery_updated']);self.assertFalse(submitted['proof_qualified'])
        with self.platform._connect() as db:
            response=json.loads(db.execute('SELECT response_json FROM learning_submissions').fetchone()[0])
        self.assertEqual(response['lab_receipt']['artifact_ref'],ref)
        reloaded_platform=LearningPlatform(self.root/'learning.sqlite3')
        recorder=ResearchEvidenceRecorder(MerlinRegistry(self.root/'registry'),HypothesisLedger(self.root/'hypotheses.sqlite3'),MerlinKnowledgeGraph(self.root/'graph.sqlite3'))
        self.bridge=self.make_bridge(reloaded_platform,recorder)
        self.assertEqual(self.run_lab(),receipt)
        self.assertTrue(self.submit()['duplicate'])
        self.assertEqual(len(self.registry.artifact_history('titan-learning',ref['logical_path'])),1)
        with self.ledger._connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM hypothesis_evidence').fetchone()[0],1)
        self.assertEqual(self.learners.attempts(learner_subject_id(self.learner.tenant_id,self.learner.actor_id)),[])

    def test_wrong_tenant_learner_role_manifest_and_lesson_are_rejected(self):
        self.publish();self.run_lab()
        other=Actor(self.learner.tenant_id,'other-learner','learner')
        self.platform.enroll(other,self.course['course_id'])
        cases=[(Actor('other-college',self.learner.actor_id,'learner'),{}),(other,{}),
               (self.teacher,{}),(self.learner,{'manifest_sha256':'0'*64}),
               (self.learner,{'lesson_id':'titan-transfer'})]
        for actor,changes in cases:
            with self.subTest(actor=actor,changes=changes),self.assertRaises((LearningPermissionError,LearningConflictError)):
                self.run_lab(actor,**changes)

    def test_tampered_canonical_artifact_cannot_be_attached_to_assessment(self):
        self.publish();receipt=self.run_lab();ref=receipt['artifact_ref']
        path=self.registry.blobs/ref['sha256'][:2]/ref['sha256'][2:]
        path.write_bytes(path.read_bytes()+b'tamper')
        with self.assertRaises((RuntimeError,ValueError)):self.submit()
        with self.platform._connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM learning_submissions').fetchone()[0],0)

    def test_stale_version_fails_new_submission_without_relabeling_existing_evidence(self):
        self.publish();receipt=self.run_lab()
        self.platform.create_revision(self.teacher,self.course['course_id'])
        with self.assertRaises(LearningConflictError):self.submit()
        self.assertEqual(receipt['artifact_ref']['version'],1)
        self.assertEqual(hashlib.sha256(self.registry.read_artifact_ref(receipt['artifact_ref'])['content']).hexdigest(),receipt['artifact_sha256'])
        self.assertEqual(self.learners.attempts(learner_subject_id(self.learner.tenant_id,self.learner.actor_id)),[])

    def test_existing_human_review_calibration_gate_and_no_automatic_mastery(self):
        self.publish();self.run_lab();self.submit()
        with self.assertRaisesRegex(LearningPermissionError,'calibration'):
            self.platform.review_submission(self.reviewer,self.course['course_id'],'known-fixture-submission','accepted',
                'Synthetic reviewer has no calibration; this must not be recorded.',{'structural_reasoning':1.0})
        with self.platform._connect() as db:
            self.assertEqual(db.execute('SELECT status FROM learning_submissions').fetchone()[0],'pending_review')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM learning_submission_reviews').fetchone()[0],0)
        self.assertEqual(self.learners.attempts(learner_subject_id(self.learner.tenant_id,self.learner.actor_id)),[])

    def test_repeatable_demo_freezes_transcript_before_lab_and_keeps_submission_pending(self):
        root=self.root/'demo';first=run_synthetic_titan_demo(root,SOURCE);second=run_synthetic_titan_demo(root,SOURCE)
        self.assertEqual(first['lab'],second['lab']);self.assertTrue(second['submission']['duplicate'])
        registry=MerlinRegistry(root/'registry')
        frozen=registry.read_artifact_ref(first['frozen_transcript_ref'])
        protocol=json.loads(frozen['content'])
        self.assertEqual(protocol['fixture_class'],'known_fixture')
        self.assertEqual(len(protocol['predictions']),5)
        self.assertIn(first['frozen_transcript_ref']['sha256'],first['lab']['binding']['prediction'])
        self.assertEqual(second['submission']['status'],'pending_review')
        self.assertTrue(second['synthetic_publication_review'])
        self.assertFalse(second['educational_efficacy_established'])
        self.assertFalse(second['cryptographic_security_verified'])


if __name__=='__main__':unittest.main()
