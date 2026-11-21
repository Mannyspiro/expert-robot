"""Frozen, public-known-fixture evaluation of the LMS evidence reader.

Expected spans come from original synthetic UTF-8 bytes, never reader output.
This is non-blind software-contract testing, not a general retrieval benchmark,
learning-efficacy study, grade, mastery judgment or cryptographic evaluation.
The fixture must accompany repository installs at tests/fixtures/; its exact
bytes are pinned below. No provider/network or additional database is used.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

if __package__ == "python.merlin":
    from ..dot_ai_os import bridge as bridge_module
else:
    from dot_ai_os import bridge as bridge_module

DotContextBridge = bridge_module.DotContextBridge
canonical = bridge_module.canonical
from .artifact_ref import ArtifactRef
from .learning_platform import Actor, LearningConflictError, LearningPlatform
from .learning_titan_course import LAB_LESSON_ID, titan_course_manifest
from .project_registry import MerlinRegistry

FIXTURE_SHA256 = 'b6b6b28f3aaea631c78fc7e06a23ca0d5d4342cfc065a3887f451f18a942b018'
CAPTURED_AT = '2026-11-18T00:00:00Z'


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _same_json(actual: Any, expected: Any) -> bool:
    """JSON identity preserves Boolean/integer distinctions Python equality loses."""
    try:
        return canonical(actual)==canonical(expected)
    except (TypeError,ValueError,RecursionError):
        return False


def load_frozen_fixture() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2]/'tests/fixtures/learning-evidence-eval-v1.json'
    raw = path.read_bytes()
    if len(raw) > 65536 or _sha(raw) != FIXTURE_SHA256:
        raise ValueError('exact frozen learning-evidence fixture required')
    value = json.loads(raw)
    dev = value['development_case_ids']; evaluation = value['evaluation_case_ids']
    if set(dev) & set(evaluation) or len(set(dev+evaluation)) != len(value['cases']):
        raise ValueError('development/evaluation case identities overlap or omit cases')
    if set(dev+evaluation) != {x['case_id'] for x in value['cases']}:
        raise ValueError('fixture case partition differs from cases')
    for source in value['sources']:
        raw = source['content'].encode('utf-8');span=source['expected_span']
        if (_sha(raw) != source['source_sha256'] or span !=
                {'start_byte':0,'end_byte':len(raw),'excerpt_sha256':_sha(raw)}):
            raise ValueError('frozen source/span integrity mismatch')
    return value


def _expected_pins(source: Mapping[str, Any], project_id: str) -> dict[str, Any]:
    base = 'context/'+source['namespace']+'/'+_sha(source['source_id'].encode())
    source_ref = ArtifactRef(project_id,base+'/source.txt',1,source['source_sha256']).to_dict()
    record = {'schema':'dot-context-record/1','namespace':source['namespace'],'source_id':source['source_id'],
        'title':source['title'],'source_url':source['source_url'],'source_version':source['source_version'],
        'epistemic':source['epistemic'],'captured_at':CAPTURED_AT,'source_ref':source_ref}
    return {'source_ref':source_ref,'record_ref':ArtifactRef(project_id,base+'/record.json',1,_sha(canonical(record))).to_dict()}


def grade_evidence_response(case_id: str, response: Any, *,
                            pinned_sources: Mapping[str, Mapping[str, Any]],
                            expected_binding: Mapping[str, Any],
                            expected_source_manifest_ref: Mapping[str, Any]) -> dict[str, Any]:
    """Check candidate citations independently against frozen original bytes.

    Pins are curator-owned expected references. Their paths, versions, source
    hashes and metadata hashes are independently reconstructed from the fixture.
    Forged self-consistent text/hash pairs cannot satisfy the byte oracle.
    """
    fixture=load_frozen_fixture();cases={x['case_id']:x for x in fixture['cases']}
    if case_id not in cases:raise ValueError('unknown frozen case ID')
    case=cases[case_id];sources={x['resource_id']:x for x in fixture['sources']};reasons=[]
    if not isinstance(pinned_sources,Mapping) or set(pinned_sources)!=set(sources):
        raise ValueError('complete curator-owned fixture pins required')
    expected_pins={}
    for resource,source in sources.items():
        pin=pinned_sources[resource]
        if not isinstance(pin,Mapping):raise ValueError('invalid source pin')
        ref=ArtifactRef.from_mapping(pin['source_ref'])
        expected_pins[resource]=_expected_pins(source,ref.project_id)
        if not _same_json(dict(pin),expected_pins[resource]):raise ValueError('curator pin differs from frozen original identity')
    if len({x['source_ref']['project_id'] for x in expected_pins.values()})!=1:
        raise ValueError('one tenant project required for this fixture')
    fields={'tenant_id','project_id','course_id','course_version','manifest_sha256'}
    if (not isinstance(expected_binding,Mapping) or set(expected_binding)!=fields
            or any(not isinstance(expected_binding[key],str) or not expected_binding[key].strip()
                   for key in ('tenant_id','project_id','course_id'))
            or type(expected_binding['course_version']) is not int or expected_binding['course_version']<1
            or not isinstance(expected_binding['manifest_sha256'],str)
            or re.fullmatch(r'[0-9a-f]{64}',expected_binding['manifest_sha256']) is None):
        raise ValueError('host-owned exact expected course binding required')
    expected_binding=dict(expected_binding)
    if expected_binding['project_id']!=next(iter(expected_pins.values()))['source_ref']['project_id']:
        raise ValueError('expected binding and curator pins use different projects')
    manifest_ref=ArtifactRef.from_mapping(expected_source_manifest_ref)
    if (manifest_ref.project_id!=expected_binding['project_id'] or manifest_ref.version!=1
            or manifest_ref.logical_path!='learning-evidence/'+_sha(canonical(expected_binding))+'/sources.json'):
        raise ValueError('host-owned source manifest does not match expected binding')
    if not isinstance(response,dict):response={};reasons.append('response_not_object')
    if not _same_json(response.get('binding'),expected_binding):reasons.append('wrong_or_missing_course_binding')
    if not _same_json(response.get('source_manifest_ref'),manifest_ref.to_dict()):reasons.append('wrong_or_missing_source_manifest_reference')
    if response.get('query')!=case['query']:reasons.append('wrong_frozen_query')
    if response.get('status')!=case['expected_status']:reasons.append('unexpected_response_state')
    if any(response.get(key,False) is not False for key in ('qualification','promotion_authority','mastery_updated')):
        reasons.append('unsupported_authority_claim')
    if response.get('answer') or response.get('generated_answer'):reasons.append('generated_answer_outside_retrieval_scope')
    citations=response.get('citations')
    if not isinstance(citations,list):citations=[];reasons.append('citations_not_list')
    actual=[]
    for index,citation in enumerate(citations):
        prefix='citation_'+str(index)+'_'
        if not isinstance(citation,dict):reasons.append(prefix+'not_object');continue
        resource=citation.get('resource_id');actual.append(resource)
        if not isinstance(resource,str) or resource not in sources:
            reasons.append(prefix+'unknown_resource');continue
        source=sources[resource];span=source['expected_span'];raw=source['content'].encode('utf-8')
        if any(not _same_json(citation.get(key),value) for key,value in expected_pins[resource].items()):
            reasons.append(prefix+'wrong_immutable_reference')
        start=citation.get('start_byte');end=citation.get('end_byte')
        if type(start) is not int or type(end) is not int or start!=span['start_byte'] or end!=span['end_byte']:
            reasons.append(prefix+'wrong_frozen_span');continue
        expected=raw[start:end]
        if citation.get('text')!=expected.decode('utf-8'):reasons.append(prefix+'bytes_differ_from_original')
        if citation.get('excerpt_sha256')!=_sha(expected):reasons.append(prefix+'wrong_excerpt_digest')
    if len(actual)!=len(set(str(x) for x in actual)):reasons.append('duplicate_citations')
    if set(str(x) for x in actual)!=set(case['expected_resource_ids']):reasons.append('unexpected_cited_source_set')
    if case['expected_status']=='requires_review':
        conflicts=response.get('conflicts',[])
        if not isinstance(conflicts,list) or 'declared-titan-name-conflict' not in {
                x.get('conflict_id') for x in conflicts if isinstance(x,dict)}:
            reasons.append('missing_declared_conflict')
    return {'case_id':case_id,'passed':not reasons,'failures':reasons,
        'expected_status':case['expected_status'],'observed_status':response.get('status'),
        'citation_count':len(citations),'fixture_class':'public_known_fixture',
        'qualification':False,'promotion_authority':False,'mastery_updated':False}


def _setup_demo(root: Path, source_commit: str):
    """Provision only synthetic actors, course resources and source snapshots."""
    from .learning_evidence import LearningEvidenceService
    fixture=load_frozen_fixture()
    if not isinstance(source_commit,str) or re.fullmatch(r'[0-9a-f]{40}',source_commit) is None:
        raise ValueError('runtime-owned exact source commit required')
    platform=LearningPlatform(root/'learning.sqlite3');registry=MerlinRegistry(root/'registry')
    tenant='synthetic-evidence-college';project='synthetic-learning-evidence'
    teacher=Actor(tenant,'synthetic-evidence-teacher','instructor')
    reviewer=Actor(tenant,'synthetic-evidence-reviewer','reviewer')
    learner=Actor(tenant,'synthetic-evidence-learner','learner')
    manifest=titan_course_manifest(source_commit)
    manifest['resources'] += [{'id':x['resource_id'],'title':x['title'],'source_uri':x['source_url'],
        'license':'CC0-1.0','creator':'Synthetic software evaluation fixture authors','language':'en',
        'epistemic':x['epistemic'],'synthetic':True,'accessibility':{'format':'UTF-8 text'}} for x in fixture['sources']]
    for lesson in manifest['lessons']:
        if lesson['id']==LAB_LESSON_ID:lesson['source_ids']=['fixture-titan-scope']
    slug='titan-evidence-fixture'
    existing=[x for x in platform.list_courses(teacher)['courses'] if x['slug']==slug]
    if existing:
        course=platform.get_course(teacher,existing[0]['course_id'])
        if course['version']!=1 or course['current_version']!=1 or course['manifest']!=manifest:
            raise LearningConflictError('synthetic evaluation course differs from frozen fixture')
    else:
        course=platform.create_course(teacher,slug,manifest['title'],manifest['description'])
        course=platform.update_manifest(teacher,course['course_id'],manifest)
    if course['status']=='draft':
        platform.review_course(reviewer,course['course_id'],1,'approved','Synthetic fixture course review, not a human/institutional attestation.')
        course=platform.publish_course(teacher,course['course_id'])
    platform.enroll(learner,course['course_id'])
    try:registry.inventory(project)
    except KeyError:registry.register_project(project,'Synthetic LMS/Titan evidence evaluation')
    context=DotContextBridge(registry,project_id=project,namespaces=('merlin',))
    pins={};curation=[]
    for source in fixture['sources']:
        pin=_expected_pins(source,project)
        try:
            if registry.read_artifact_ref(pin['source_ref'])['content']!=source['content'].encode():
                raise LearningConflictError('frozen source snapshot differs')
            registry.read_artifact_ref(pin['record_ref'])
        except KeyError:
            acquired=context.ingest(namespace=source['namespace'],source_id=source['source_id'],title=source['title'],
                content=source['content'].encode(),source_url=source['source_url'],source_version=source['source_version'],
                epistemic=source['epistemic'],captured_at=CAPTURED_AT)
            if any(acquired[key]!=pin[key] for key in pin):raise LearningConflictError('source acquisition identity differs from frozen fixture')
        pins[source['resource_id']]=pin
        curation.append({'resource_id':source['resource_id'],**pin,'review_note':'Original synthetic CC0 text; fixture scope and source metadata reviewed.'})
    service=LearningEvidenceService(platform,registry,tenant_projects={tenant:project},namespaces=('merlin',))
    scope={'course_id':course['course_id'],'course_version':course['version'],'manifest_sha256':course['manifest_sha256']}
    frozen=service.provision_course_sources(teacher,**scope,sources=curation,conflicts=fixture['conflicts'])
    return fixture,platform,registry,context,service,teacher,learner,scope,pins,frozen


def evaluate_evidence_reader(service, registry: MerlinRegistry, learner: Actor, *,
        course_scope: Mapping[str, Any], pinned_sources: Mapping[str, Mapping[str, Any]],
        source_manifest_ref: Mapping[str, Any], source_commit: str,
        lesson_id: str | None = None) -> dict[str, Any]:
    """Freeze the candidate scope, run real retrieval, preserve every failure.

    Optional lesson scoping is a different candidate, with a distinct protocol.
    Expected answers remain the same; a restricted candidate may legitimately
    fail these course-wide fixtures. This never silently weakens expectations.
    """
    fixture=load_frozen_fixture();scope=dict(course_scope);pins=pinned_sources
    if not isinstance(source_commit,str) or re.fullmatch(r'[0-9a-f]{40}',source_commit) is None:
        raise ValueError('runtime-owned exact source commit required')
    if lesson_id is not None:
        if not isinstance(lesson_id,str) or not lesson_id or len(lesson_id)>100:raise ValueError('bounded lesson ID required')
        scope['lesson_id']=lesson_id
    project=next(iter(pins.values()))['source_ref']['project_id']
    expected_binding={'tenant_id':learner.tenant_id,'project_id':project,
        'course_id':scope['course_id'],'course_version':scope['course_version'],'manifest_sha256':scope['manifest_sha256']}
    from . import learning_evidence as reader_module
    protocol={'schema':'merlin-learning-evidence-eval-protocol/1','fixture_sha256':FIXTURE_SHA256,
        'source_commit':source_commit,'course':scope,'expected_binding':expected_binding,'pinned_sources':pins,
        'source_manifest_ref':dict(source_manifest_ref),'case_ids':[x['case_id'] for x in fixture['cases']],
        'runtime_source_sha256':{key:_sha(Path(path).read_bytes()) for key,path in
            [('reader',reader_module.__file__),('bridge',bridge_module.__file__),('evaluator',__file__)]},
        'development_case_ids':fixture['development_case_ids'],'evaluation_case_ids':fixture['evaluation_case_ids'],
        'limits':fixture['limits'],'qualification':False,'promotion_authority':False}
    base='learning-evidence-eval/'+_sha(canonical(protocol))
    registry.put_artifact(project,base+'/protocol.json',canonical(protocol),'application/json')
    protocol_ref=registry.artifact_ref(project,base+'/protocol.json')
    results=[]
    for case in fixture['cases']:
        try:response=service.retrieve(learner,**scope,query=case['query'],limit=6,budget_bytes=16000)
        except Exception as exc:response={'status':'reader_error','citations':[],'error_class':type(exc).__name__,'error':str(exc)[:1000]}
        candidate_path=base+'/candidates/'+case['case_id']+'.json'
        registry.put_artifact(project,candidate_path,canonical(response),'application/json')
        result=grade_evidence_response(case['case_id'],response,pinned_sources=pins,
            expected_binding=expected_binding,expected_source_manifest_ref=source_manifest_ref)
        results.append({**result,'candidate_ref':registry.artifact_ref(project,candidate_path)})
    metrics={'case_count':len(results),'passed':sum(x['passed'] for x in results),
        'failed':sum(not x['passed'] for x in results),
        'development_passed':sum(x['passed'] for x in results if x['case_id'] in fixture['development_case_ids']),
        'evaluation_passed':sum(x['passed'] for x in results if x['case_id'] in fixture['evaluation_case_ids'])}
    report={'schema':'merlin-learning-evidence-eval-report/1','fixture_class':'public_known_fixture',
        'fixture_sha256':FIXTURE_SHA256,'protocol_ref':protocol_ref,'metrics':metrics,'cases':results,
        'source_sha256':{x['resource_id']:x['source_sha256'] for x in fixture['sources']},
        'limits':fixture['limits'],'mastery_updated':False,'qualification':False,'promotion_authority':False}
    registry.put_artifact(project,base+'/report.json',canonical(report),'application/json')
    return {'schema':'synthetic-learning-evidence-demo/1','fixture_class':'public_known_fixture',
        'fixture_sha256':FIXTURE_SHA256,'metrics':metrics,'protocol_ref':protocol_ref,
        'report_ref':registry.artifact_ref(project,base+'/report.json'),
        'case_sha256':_sha(canonical(fixture['cases'])),'source_sha256':report['source_sha256'],
        'mastery_updated':False,'qualification':False,'promotion_authority':False,'limits':fixture['limits']}


def run_synthetic_evidence_demo(root: str | Path, source_commit: str) -> dict[str, Any]:
    """Repeatable synthetic publication/enrollment/curation and reader evaluation."""
    _,_,registry,_,service,_,learner,scope,pins,frozen=_setup_demo(Path(root),source_commit)
    return evaluate_evidence_reader(service,registry,learner,course_scope=scope,pinned_sources=pins,
        source_manifest_ref=frozen['source_manifest_ref'],source_commit=source_commit)


__all__=['load_frozen_fixture','grade_evidence_response','evaluate_evidence_reader','run_synthetic_evidence_demo','FIXTURE_SHA256']
