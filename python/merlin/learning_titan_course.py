"""Curated draft Titan course and a synthetic, local persistence demonstration.

Titan here means envelope/protocol structural research, separate from historical
CPU-fabric naming. The builder never publishes a course. The demonstration uses
explicitly synthetic teacher/reviewer/learner actors; its publication review is
a fixture, not a human attestation. No cryptography, provider, network, mastery,
educational efficacy, qualification or promotion is implemented or claimed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .learning_platform import Actor, LearningConflictError, LearningPlatform, SCHEMA
from .titan_protocol_model import build_titan_protocol_bundle, canonical_json_bytes

LAB_LESSON_ID = 'titan-structural-lab'
LAB_TASK_ID = 'titan-structural-model-v1'
COURSE_SLUG = 'titan-structural-research'


def _commit(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{40}', value) is None:
        raise ValueError('runtime-owned full lowercase source commit required')
    return value


def titan_course_manifest(source_commit: str) -> dict[str, Any]:
    """Return a fresh, source-pinned manifest suitable for instructor review.

    The host supplies the reviewed source revision. Links are citations, not
    fetched content or proof that the running checkout matches that revision.
    Rights are unresolved: resources link to repository originals, not licensed
    copies of external media. The model/vector hashes bind this runtime's model.
    """
    commit = _commit(source_commit)
    bundle = build_titan_protocol_bundle(kem='ML-KEM-768')
    paths = [
        ('model', 'Executable structural model and canonical vectors', 'python/merlin/titan_protocol_model.py'),
        ('protocol-notes', 'Titan protocol model scope and vector limitations', 'docs/merlin/TITAN_PROTOCOL_MODEL_AND_VECTORS_V1.md'),
        ('formal-spec', 'Abstract transition specification', 'formal/MathAI/TitanProtocol.lean'),
        ('titan-research', 'Titan research and experimental boundaries', 'docs/merlin/MERLIN_TITAN_IDEONOMY_FUTURE_TECH_V1.md'),
        ('lms-blueprint', 'Merlin Learning product proposal', 'docs/merlin/MERLIN_LEARNING_UNIVERSITY_LMS_BLUEPRINT_V0_1.md'),
    ]
    resources = [{'id': identifier, 'title': title,
        'source_uri': 'https://github.com/Mannyspiro/expert-robot/blob/'+commit+'/'+path,
        'source_commit': commit, 'source_path': path, 'creator': 'Expert Robot repository contributors',
        'license': 'Repository rights not established; link-only; redistribution requires rights review',
        'language': 'en', 'accessibility': {'text_alternative': True, 'format': 'source text'},
        'review_status': 'requires_instructor_source_and_accessibility_review'} for identifier, title, path in paths]
    objectives = [
        {'id': 'TITAN-SCOPE', 'title': 'Separate structure, implementation and security claims',
         'description': 'Explain what canonical bytes and abstract protocol transitions establish, and list missing cryptographic and empirical evidence.',
         'prerequisites': [], 'dimensions': ['conceptual_explanation', 'source_provenance', 'limitations']},
        {'id': 'TITAN-STRUCTURE', 'title': 'Predict and reproduce envelope structural rejection',
         'description': 'Freeze predictions, reproduce five known fixtures and attach exact canonical model/vector evidence with rejection explanations.',
         'prerequisites': ['TITAN-SCOPE'], 'dimensions': ['procedure', 'reproducibility', 'estimation_error_detection']},
        {'id': 'TITAN-TRANSFER', 'title': 'Challenge a structural acceptance claim in a new context',
         'description': 'Construct a novel counterexample or boundary argument; map invariants to another protocol and explain what the analogy loses.',
         'prerequisites': ['TITAN-STRUCTURE'], 'dimensions': ['transfer', 'proof_justification', 'critical_interpretation']},
    ]
    rubric = [
        {'dimension': 'prediction_and_provenance', 'points': 3,
         'description': 'Records predictions before execution; cites exact course version, model/vector identities and immutable evidence. Distinguishes public known fixtures from held-out evaluation.'},
        {'dimension': 'structural_reasoning', 'points': 3,
         'description': 'Explains each accepted/rejected case and the authenticated-before-accepted abstract sequence; does not infer executed authentication from a state label.'},
        {'dimension': 'transfer_and_counterexample', 'points': 3,
         'description': 'Provides a new boundary case or mapped analogue, explicit assumptions/invariants and an original acceptance test. States losses and unresolved implementation behavior.'},
        {'dimension': 'limits_and_reflection', 'points': 3,
         'description': 'Separates artifact integrity, structural consistency, proof assumptions, cryptographic security and learning efficacy; records mismatch or uncertainty without hiding negative results.'},
    ]
    return {'schema': SCHEMA, 'title': 'Titan: evidence and structural protocol models',
        'description': 'A reviewed research-literacy course using a deterministic envelope model. This is not encryption training data, a cipher implementation, or a security certification.',
        'modules': [{'id': 'titan-research-literacy', 'title': 'From a protocol claim to checkable evidence',
                     'objective_ids': [x['id'] for x in objectives]}],
        'objectives': objectives,
        'lessons': [
            {'id': 'titan-scope', 'title': 'Start with the claim and its limits', 'objective_id': 'TITAN-SCOPE',
             'body': 'From memory, distinguish an envelope schema, a protocol-state specification, an implementation and a security argument. Titan here concerns encryption/protocol structural research, not the historical CPU-fabric name. The model names HKDF-SHA-256, AES-256-GCM-SIV and an optional ML-KEM profile; it executes none of those primitives. Trace initialized -> key_established -> keys_derived -> sealed -> authenticated -> accepted. Explain why rejected and accepted are terminal in this abstract model. A Lean theorem about that relation does not establish primitive conformance or side-channel resistance. Read the pinned source before trusting this summary.',
             'source_ids': ['model', 'protocol-notes', 'formal-spec'], 'estimated_minutes': 15,
             'exercise': {'task_id': 'titan-scope-explanation-v1', 'prompt': 'Give one justified structural claim and three claims requiring different evidence. Identify which evidence could falsify each.'}},
            {'id': LAB_LESSON_ID, 'title': 'Freeze a prediction, then run the fixed structural lab', 'objective_id': 'TITAN-STRUCTURE',
             'body': 'Before running, preserve a short transcript with your predictions for valid structure, missing context, an unapproved suite, experimental-field contamination and unsupported version. These five fixtures and their expected outcomes are public known fixtures, not a held-out test. Run only the fixed lab; compare observed structural rejections with your frozen predictions, explain discrepancies and cite the exact ArtifactRef. Placeholder nonce/ciphertext/tag fields are opaque strings and are not decryptable known-answer vectors. A successful run cannot award mastery or establish crypto security. Write a reflection for a calibrated independent human reviewer.',
             'source_ids': ['model', 'protocol-notes'], 'estimated_minutes': 20,
             'exercise': {'task_id': LAB_TASK_ID, 'lab_kind': 'titan_structural_model',
                          'fixture_class': 'known_fixture', 'prediction_required': True,
                          'prompt': 'Predict the five structural outcomes, then explain observed evidence, disagreement and missing security evidence.'}},
            {'id': 'titan-transfer', 'title': 'Transfer and skeptical review', 'objective_id': 'TITAN-TRANSFER',
             'body': 'Transfer exercise: a different service supplies all required context fields as non-empty strings, but authenticates a different encoding or binds the wrong tenant. Explain why structural acceptance alone may miss the defect. Map the envelope identity/context/authentication-order invariants to a document-signing workflow and state where the analogy fails. Propose one original discriminating test and a negative control without inventing keys, ciphertext or a security result. Consider simplex weights only for competing explanation allocation, n-arity for independent field/role axes, a continuum only if a justified quantitative approximation exists, and fuzzy membership only for explanatory similarity; Boolean authorization/integrity checks remain exact. Give apply/defer/not-applicable reasons rather than forcing a representation.',
             'source_ids': ['model', 'protocol-notes', 'titan-research'], 'estimated_minutes': 20,
             'exercise': {'task_id': 'titan-transfer-review-v1', 'prompt': 'Submit a new counterexample, invariant mapping, falsifier, negative control and a statement of what remains unknown.'}},
        ],
        'assessments': [{'id': 'assess-'+objective['id'].lower(), 'title': objective['title'],
            'objective_id': objective['id'], 'high_stakes': False, 'human_review_required': True,
            'rubric': json.loads(json.dumps(rubric)), 'calibration_policy': 'existing tenant-attested reviewer calibration; no automatic grade or mastery'} for objective in objectives],
        'resources': resources, 'grading_policy': {'automated_high_stakes': False, 'automatic_mastery': False,
            'human_review_required': True, 'evidence_integrity_is_grade': False},
        'research_scope': {'fixture_class': 'known_fixture', 'source_commit': commit,
            'model_schema': bundle['model']['schema'], 'model_sha256': bundle['model_sha256'],
            'vectors_schema': bundle['vectors']['schema'], 'vectors_sha256': bundle['vectors_sha256'],
            'cryptographic_operations_implemented': False, 'cryptographic_security_verified': False,
            'educational_efficacy_established': False, 'qualification': False, 'promotion_authority': False}}


def create_titan_course(platform: LearningPlatform, teacher: Actor, source_commit: str,
                        slug: str = COURSE_SLUG) -> dict[str, Any]:
    """Create an instructor-owned draft; existing publication policy is retained."""
    manifest = titan_course_manifest(source_commit)
    course = platform.create_course(teacher, slug, manifest['title'], manifest['description'])
    return platform.update_manifest(teacher, course['course_id'], manifest)


def run_synthetic_titan_demo(root: str | Path, source_commit: str) -> dict[str, Any]:
    """Repeatable local synthetic run; no calibrated review or learner score.

    Host-owned root must be dedicated to this example. Replaying on the same
    root preserves its published version, pre-run transcript, lab and submission.
    """
    from .hypothesis_ledger import HypothesisLedger
    from .knowledge_graph import MerlinKnowledgeGraph
    from .learner_model import LearnerStore
    from .learning_lab_bridge import LearningLabBridge
    from .project_registry import MerlinRegistry
    from .research_evidence import ResearchEvidenceRecorder

    commit = _commit(source_commit); root = Path(root)
    platform = LearningPlatform(root/'learning.sqlite3')
    learners = LearnerStore(root/'learning.sqlite3')
    teacher = Actor('synthetic-college', 'synthetic-teacher', 'instructor')
    reviewer = Actor('synthetic-college', 'synthetic-reviewer', 'reviewer')
    learner = Actor('synthetic-college', 'synthetic-learner', 'learner')
    courses = [x for x in platform.list_courses(teacher)['courses'] if x['slug'] == COURSE_SLUG]
    if courses:
        course = platform.get_course(teacher,courses[0]['course_id'])
        if course['version'] != 1 or course['current_version'] != 1 or course['manifest'] != titan_course_manifest(commit):
            raise LearningConflictError('synthetic demo course differs from its source-pinned fixture')
    else: course = create_titan_course(platform,teacher,commit)
    if course['status'] == 'draft':
        platform.review_course(reviewer,course['course_id'],course['version'],'approved',
            'Synthetic fixture review; not a human attestation or institutional publication approval.')
        course = platform.publish_course(teacher,course['course_id'])
    platform.enroll(learner,course['course_id'])
    registry = MerlinRegistry(root/'registry'); project = 'titan-learning-demo'
    try: registry.inventory(project)
    except KeyError: registry.register_project(project,'Synthetic Titan learning evidence')
    recorder = ResearchEvidenceRecorder(registry,HypothesisLedger(root/'hypotheses.sqlite3'),MerlinKnowledgeGraph(root/'graph.sqlite3'))
    transcript = {'schema':'synthetic-titan-frozen-transcript/1','fixture_class':'known_fixture',
        'tenant_id':learner.tenant_id,'learner_id':learner.actor_id,'course_id':course['course_id'],
        'course_version':course['version'],'manifest_sha256':course['manifest_sha256'],'source_commit':commit,
        'predictions':{'valid-envelope-structure':True,'missing-context':False,'unapproved-suite':False,
            'experimental-field-contamination':False,'unsupported-version':False},
        'transcript':[{'speaker':'synthetic-learner','text':'I predict the public structural fixtures only; no ciphertext or authentication will be executed.'}],
        'acceptance':'Compare exact deterministic structural outcomes and preserve evidence; never infer efficacy/security/mastery.'}
    path = 'learning/synthetic-demo/frozen-transcript.json'; raw = canonical_json_bytes(transcript)
    try:
        frozen = registry.artifact_ref(project,path,version=1)
        if registry.read_artifact_ref(frozen)['content'] != raw: raise LearningConflictError('frozen demo transcript differs')
    except KeyError:
        registry.put_artifact(project,path,raw); frozen = registry.artifact_ref(project,path,version=1)
    bridge = LearningLabBridge(platform,recorder,tenant_projects={learner.tenant_id:project},source_commit=commit)
    args = {'course_id':course['course_id'],'course_version':course['version'],
        'manifest_sha256':course['manifest_sha256'],'lesson_id':LAB_LESSON_ID,'run_id':'synthetic-titan-run-1'}
    lab = bridge.run_titan_lab(learner,**args,prediction='Frozen known-fixture predictions/transcript ArtifactRef: '+json.dumps(frozen,sort_keys=True))
    submission = bridge.submit_lab_assessment(learner,**args,submission_id='synthetic-titan-submission-1',
        reflection='Public known fixtures reproduce structural acceptance/rejection. The wrong-tenant authenticated-data transfer case still needs an implementation test. This run establishes no crypto security, educational efficacy or mastery.')
    # Use the existing learner store without inserting uncalibrated scores.
    recommendation = platform.recommend_next_lesson(learner,course['course_id'],learners)
    return {'schema':'synthetic-titan-learning-demo/1','fixture_class':'known_fixture',
        'course_id':course['course_id'],'version':course['version'],'manifest_sha256':course['manifest_sha256'],
        'frozen_transcript_ref':frozen,'lab':lab,'submission':submission,
        'recommendation_sha256':hashlib.sha256(canonical_json_bytes(recommendation)).hexdigest(),
        'synthetic_publication_review':True,'mastery_updated':False,'proof_qualified':False,
        'cryptographic_security_verified':False,'educational_efficacy_established':False,'promotion_authority':False}


__all__ = ['titan_course_manifest','create_titan_course','run_synthetic_titan_demo','LAB_LESSON_ID','LAB_TASK_ID']
