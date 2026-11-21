"""Synthetic HTTP/identity boundary and narrow real-app POST route tests.

The app method is extracted from its actual source, without importing/seeding
the unrelated full application. This is not a full app startup/deployment test.
Canonical LMS/registry/evidence stores are real; the host authentication resolver
is an explicit synthetic fixture, not institutional SSO or a live attestation.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager
from copy import deepcopy
import errno
from http import client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
from time import perf_counter
import unittest
from urllib.parse import urlparse, urlsplit

from merlin.learning_evidence_eval import _setup_demo, grade_evidence_response
from merlin.learning_platform import Actor, LearningPlatform
from merlin.project_registry import MerlinRegistry
from merlin.learning_research_api import LearningResearchAPI
from merlin.learning_lab_bridge import LearningLabBridge
from merlin.hypothesis_ledger import HypothesisLedger
from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.research_evidence import ResearchEvidenceRecorder


COMMIT='c'*40
TOKEN_MARKER='synthetic-token-must-not-leak'
RAW_MARKER='untrusted raw source marker must not leak'


def _app_method(name, globals_):
    """Compile one actual nested method, retaining original filename/line data."""
    path=Path(__file__).resolve().parents[1]/'python/merlin/app.py'
    tree=ast.parse(path.read_text())
    handlers=[node for node in ast.walk(tree) if isinstance(node,ast.ClassDef) and node.name=='Handler']
    if len(handlers)!=1:raise AssertionError('one actual application Handler required')
    methods=[node for node in handlers[0].body if isinstance(node,ast.FunctionDef) and node.name==name]
    if len(methods)!=1:raise AssertionError('one actual app method required: '+name)
    scope=dict(globals_)
    exec(compile(ast.Module(body=[deepcopy(methods[0])],type_ignores=[]),str(path),'exec'),scope)
    return scope[name]


def _app_factory_guards():
    """Compile only actual factory guard prelude, before any app construction."""
    path=Path(__file__).resolve().parents[1]/'python/merlin/app.py'
    tree=ast.parse(path.read_text())
    factory=deepcopy(next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='make_handler'))
    prefix=[]
    for statement in factory.body:
        if (isinstance(statement,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='simulation' for target in statement.targets)):
            break
        prefix.append(statement)
    else:raise AssertionError('app guard/initialization boundary changed')
    for argument in factory.args.posonlyargs+factory.args.args+factory.args.kwonlyargs:argument.annotation=None
    if factory.args.vararg:factory.args.vararg.annotation=None
    if factory.args.kwarg:factory.args.kwarg.annotation=None
    factory.returns=None
    factory.body=prefix+[ast.Return(value=ast.Tuple(elts=[ast.Name(id=name,ctx=ast.Load())
        for name in ('learning_platform','canonical_registry')],ctx=ast.Load()))]
    module=ast.fix_missing_locations(ast.Module(body=[factory],type_ignores=[]))
    scope={'LearningResearchAPI':LearningResearchAPI};exec(compile(module,str(path),'exec'),scope)
    return scope['make_handler']


@contextmanager
def _loopback(test,handler):
    try:server=ThreadingHTTPServer(('127.0.0.1',0),handler)
    except OSError as exc:
        if exc.errno==errno.EPERM:test.skipTest('sandbox denies loopback bind with EPERM; OCI must run this test')
        raise
    thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.01},daemon=True)
    thread.start()
    try:yield server.server_address
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)
        if thread.is_alive():raise AssertionError('synthetic loopback server did not stop')


def _post(address,path,payload,*,token='learner',headers=None):
    body=payload if isinstance(payload,bytes) else json.dumps(payload).encode()
    supplied={'Content-Type':'application/json','Content-Length':str(len(body))}
    if token is not None:supplied['Authorization']='Bearer '+token
    supplied.update(headers or {})
    connection=client.HTTPConnection(*address,timeout=5)
    try:
        connection.request('POST',path,body,headers=supplied)
        response=connection.getresponse();raw=response.read()
        return response.status,json.loads(raw)
    finally:connection.close()


def _handler(api,*,actual_app=False):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def _send(self,status,payload):
            raw=json.dumps(payload,sort_keys=True).encode()
            self.send_response(status);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def do_POST(self):
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=131072:raise ValueError('bounded body required')
                data=LearningResearchAPI.decode_body(self.rfile.read(length))
            except (ValueError,UnicodeError):self._send(400,{'error':'invalid_research_request'});return
            result=api.dispatch(urlparse(self.path).path,self.headers,data)
            self._send(*(result if result is not None else (404,{'error':'not_found'})))
    if actual_app:
        class NeverUsed(Exception):pass
        globals_={'perf_counter':perf_counter,'urlparse':urlparse,'urlsplit':urlsplit,'json':json,
            'MAX_BODY':1000000,'learning_research_api':api,'LearningResearchAPI':LearningResearchAPI,
            'LeaseConflict':NeverUsed,'URLError':NeverUsed,'HTTPError':NeverUsed,'Any':object}
        Handler.do_POST=_app_method('do_POST',globals_)
        Handler._origin_allowed=_app_method('_origin_allowed',globals_)
    return Handler


class LearningResearchAPITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.fixture,self.platform,self.registry,self.context,self.service,self.teacher,
            self.learner,self.scope,self.pins,self.frozen)=_setup_demo(self.root,COMMIT)
        self.reviewer=Actor(self.learner.tenant_id,'synthetic-evidence-reviewer','reviewer')
        self.foreign=Actor('foreign-synthetic-college',self.learner.actor_id,'learner')
        self.unenrolled=Actor(self.learner.tenant_id,'unenrolled-synthetic-learner','learner')
        self.other_teacher=Actor(self.learner.tenant_id,'other-synthetic-teacher','instructor')
        self.actors={'learner':self.learner,'teacher':self.teacher,'reviewer':self.reviewer,
            'foreign':self.foreign,'unenrolled':self.unenrolled,'other-teacher':self.other_teacher}
        self.resolutions=[]
        def resolve(headers):
            self.resolutions.append(True)
            return self.actors.get(str(headers.get('Authorization','')).removeprefix('Bearer '))
        self.resolver=resolve
        self.api=LearningResearchAPI(self.platform,self.service,self.resolver)
        self.base='/api/learning/courses/'+self.scope['course_id']+'/research/'
        self.body={key:self.scope[key] for key in ('course_version','manifest_sha256')}

    def call(self,action='evidence',*,api=None,token='learner',body=None,extra=None):
        value={**self.body,'query':'placeholder decryptable'} if body is None else dict(body)
        value.update(extra or {})
        headers={} if token is None else {'Authorization':'Bearer '+token}
        return (api or self.api).dispatch(self.base+action,headers,value)

    def assert_redacted(self,payload):
        raw=json.dumps(payload)
        self.assertNotIn(TOKEN_MARKER,raw);self.assertNotIn(RAW_MARKER,raw)
        self.assertNotIn(self.fixture['sources'][0]['content'],raw)
        self.assertNotIn('Titan structural lab',raw)

    def grade(self,case_id,response):
        return grade_evidence_response(case_id,response,pinned_sources=self.pins,
            expected_binding={'tenant_id':self.learner.tenant_id,'project_id':'synthetic-learning-evidence',**self.scope},
            expected_source_manifest_ref=self.frozen['source_manifest_ref'])

    def curation(self):
        return {**self.body,'sources':[{'resource_id':source['resource_id'],**self.pins[source['resource_id']],
            'review_note':'Original synthetic CC0 text; fixture scope and source metadata reviewed.'} for source in self.fixture['sources']],
            'conflicts':self.fixture['conflicts']}

    def test_missing_resolver_service_and_invalid_constructor_fail_closed(self):
        status,payload=self.call(api=LearningResearchAPI(self.platform,self.service,None))
        self.assertEqual(status,503);self.assert_redacted(payload)
        status,payload=self.call(api=LearningResearchAPI(self.platform,None,self.resolver))
        self.assertEqual(status,503);self.assert_redacted(payload)
        with self.assertRaises(ValueError):LearningResearchAPI(self.platform,self.service,'caller-supplied-token')
        with self.assertRaises(ValueError):
            LearningResearchAPI(LearningPlatform(self.root/'different-learning.sqlite3'),self.service,self.resolver)

    def test_actual_app_factory_guard_prelude_requires_identical_host_objects(self):
        # This prelude exits before simulation, application imports or seeding.
        guards=_app_factory_guards()
        args={'store':None,'learning_research_api':self.api,'learning_platform':self.platform,
            'learning_identity_resolver':self.resolver,'canonical_registry':self.registry}
        self.assertEqual(guards(**args),(self.platform,self.registry))
        for change in ({'learning_platform':LearningPlatform(self.root/'guard-learning.sqlite3')},
                       {'learning_identity_resolver':lambda headers:self.learner},
                       {'canonical_registry':MerlinRegistry(self.root/'guard-registry')},
                       {'learning_research_api':object()}):
            with self.subTest(change=next(iter(change))),self.assertRaises(ValueError):guards(**{**args,**change})

    def test_missing_invalid_or_exceptional_authentication_never_leaks(self):
        for token in (None,'invalid-'+TOKEN_MARKER):
            with self.subTest(token=token):
                status,payload=self.call(token=token);self.assertEqual(status,401);self.assert_redacted(payload)
        for invalid in ({'tenant_id':self.learner.tenant_id,'actor_id':self.learner.actor_id,'role':'learner'},
                        Actor(self.learner.tenant_id,self.learner.actor_id,'forged-admin')):
            api=LearningResearchAPI(self.platform,self.service,lambda headers:invalid)
            status,payload=self.call(api=api);self.assertEqual(status,401);self.assert_redacted(payload)
        def broken(headers):raise RuntimeError(TOKEN_MARKER+' '+RAW_MARKER)
        status,payload=self.call(api=LearningResearchAPI(self.platform,self.service,broken))
        self.assertEqual(status,401);self.assert_redacted(payload)

    def test_body_cannot_supply_identity_project_course_or_authority(self):
        for key in ('actor','tenant_id','learner_id','role','principal','project_id','course_id','authorization','approval','promotion_authority'):
            with self.subTest(field=key):
                status,payload=self.call(extra={key:TOKEN_MARKER+' '+RAW_MARKER})
                self.assertEqual(status,400);self.assert_redacted(payload)
        status,_=self.api.dispatch(self.base+'evidence',{'Authorization':'Bearer learner','X-Role':'tenant_admin','X-Tenant-Id':'wrong'},
            {**self.body,'query':'placeholder decryptable'})
        self.assertEqual(status,200)

    def test_tenant_course_enrollment_version_and_manifest_boundaries(self):
        for token in ('foreign','unenrolled','teacher'):
            with self.subTest(token=token):
                status,payload=self.call(token=token);self.assertEqual(status,403);self.assert_redacted(payload)
        for change in ({'manifest_sha256':'0'*64},{'course_version':2}):
            status,payload=self.call(extra=change);self.assertIn(status,(403,409));self.assert_redacted(payload)
        for value in (True,1.0,0,-1):
            status,payload=self.call(extra={'course_version':value});self.assertEqual(status,400);self.assert_redacted(payload)
        status,payload=self.api.dispatch('/api/learning/courses/not-this-course/research/evidence',
            {'Authorization':'Bearer learner'},{**self.body,'query':'placeholder'})
        self.assertIn(status,(403,409));self.assert_redacted(payload)

    def test_curator_source_freeze_and_owner_restrictions(self):
        for token in ('learner','reviewer','other-teacher','foreign'):
            status,payload=self.call('sources',token=token,body=self.curation())
            self.assertEqual(status,403);self.assert_redacted(payload)
        status,payload=self.call('sources',token='teacher',body=self.curation())
        self.assertEqual(status,200);self.assertEqual(payload['source_manifest_ref'],self.frozen['source_manifest_ref'])
        changed=self.curation();changed['sources'][0]['review_note']=RAW_MARKER
        status,payload=self.call('sources',token='teacher',body=changed)
        self.assertEqual(status,409);self.assert_redacted(payload)
        for missing in ('record_ref','source_ref'):
            malformed=self.curation();malformed['sources'][0].pop(missing)
            with self.subTest(missing=missing):
                status,payload=self.call('sources',token='teacher',body=malformed)
                self.assertEqual(status,400);self.assert_redacted(payload)

    def test_real_citations_conflict_abstention_and_exact_replay(self):
        for case in self.fixture['cases']:
            with self.subTest(case=case['case_id']):
                body={**self.body,'query':case['query']}
                status,payload=self.call(body=body)
                self.assertEqual(status,200);self.assertTrue(self.grade(case['case_id'],payload)['passed'])
                self.assertEqual(self.call(body=body),(status,payload))

    def test_malformed_and_bounded_json_decoder_and_unknown_route(self):
        invalid=[b'{',b'[]',b'{"query":NaN}',b'{"query":"a","query":"b"}',b'\xff',b' ' * 131073]
        for raw in invalid:
            with self.subTest(raw=raw[:30]),self.assertRaises((ValueError,UnicodeError)):
                LearningResearchAPI.decode_body(raw)
        nested={};cursor=nested
        for _ in range(20):cursor['deep']={};cursor=cursor['deep']
        for value in (nested,{'nodes':['x']*5000}):
            with self.assertRaises(ValueError):LearningResearchAPI.decode_body(json.dumps(value).encode())
        before=len(self.resolutions)
        self.assertIsNone(self.api.dispatch('/not-a-research-route',{},{}))
        self.assertEqual(len(self.resolutions),before)
        for suffix in ('unknown','evidence/extra','%2e%2e','../evidence'):
            self.assertFalse(LearningResearchAPI.matches_path(self.base+suffix))

    def test_integrity_errors_hide_raw_source_and_do_not_return_citations(self):
        ref=self.pins['fixture-titan-scope']['source_ref']
        blob=self.registry.blobs/ref['sha256'][:2]/ref['sha256'][2:]
        blob.write_bytes((TOKEN_MARKER+' '+RAW_MARKER).encode())
        status,payload=self.call();self.assertEqual(status,503);self.assert_redacted(payload)
        self.assertNotIn('citations',payload)

    def test_optional_real_lab_replay_and_pending_review_without_mastery(self):
        recorder=ResearchEvidenceRecorder(self.registry,HypothesisLedger(self.root/'hypotheses.sqlite3'),MerlinKnowledgeGraph(self.root/'graph.sqlite3'))
        bridge=LearningLabBridge(self.platform,recorder,tenant_projects={self.learner.tenant_id:'synthetic-learning-evidence'},source_commit=COMMIT)
        api=LearningResearchAPI(self.platform,self.service,self.resolver,lab_bridge=bridge)
        body={**self.body,'lesson_id':'titan-structural-lab','run_id':'synthetic-http-lab',
            'prediction':'Known public structural fixtures reproduce their declared outcomes; no crypto operations.'}
        status,lab=self.call('lab',api=api,body=body);self.assertEqual(status,200)
        self.assertFalse(lab['mastery_updated']);self.assertEqual(self.call('lab',api=api,body=body),(status,lab))
        submission={key:value for key,value in body.items() if key!='prediction'}
        submission.update(submission_id='synthetic-http-submission',reflection='Known fixtures only; authentication/security and transfer understanding remain unmeasured.')
        status,result=self.call('submit-lab',api=api,body=submission);self.assertEqual(status,200)
        self.assertEqual(result['status'],'pending_review');self.assertFalse(result['mastery_updated'])
        self.assertTrue(self.call('submit-lab',api=api,body=submission)[1]['duplicate'])
        status,payload=self.call('lab',body=body);self.assertEqual(status,503);self.assert_redacted(payload)

    def test_actual_loopback_dispatcher_transport(self):
        with _loopback(self,_handler(self.api)) as address:
            for case in self.fixture['cases']:
                status,payload=_post(address,self.base+'evidence',{**self.body,'query':case['query']})
                self.assertEqual(status,200);self.assertTrue(self.grade(case['case_id'],payload)['passed'])
            status,payload=_post(address,self.base+'evidence',{**self.body,'query':'placeholder'},token=TOKEN_MARKER)
            self.assertEqual(status,401);self.assert_redacted(payload)
            status,payload=_post(address,self.base+'evidence',b'{"query":"'+RAW_MARKER.encode()+b'",}')
            self.assertEqual(status,400);self.assert_redacted(payload)
            status,_=_post(address,self.base+'unknown',self.body);self.assertEqual(status,404)

    def test_actual_app_do_post_narrow_route_dispatch_over_loopback(self):
        # Only actual do_POST and _origin_allowed are compiled. All unrelated
        # app construction/default-store seeding/provider imports are excluded.
        recorder=ResearchEvidenceRecorder(self.registry,HypothesisLedger(self.root/'app-hypotheses.sqlite3'),MerlinKnowledgeGraph(self.root/'app-graph.sqlite3'))
        bridge=LearningLabBridge(self.platform,recorder,tenant_projects={self.learner.tenant_id:'synthetic-learning-evidence'},source_commit=COMMIT)
        api=LearningResearchAPI(self.platform,self.service,self.resolver,lab_bridge=bridge)
        with _loopback(self,_handler(api,actual_app=True)) as address:
            status,payload=_post(address,self.base+'sources',self.curation(),token='teacher')
            self.assertEqual(status,200);self.assertEqual(payload['source_manifest_ref'],self.frozen['source_manifest_ref'])
            for case in self.fixture['cases']:
                status,payload=_post(address,self.base+'evidence',{**self.body,'query':case['query']})
                self.assertEqual(status,200);self.assertTrue(self.grade(case['case_id'],payload)['passed'])
            lab_body={**self.body,'lesson_id':'titan-structural-lab','run_id':'synthetic-app-http-lab',
                'prediction':'Known public structural outcomes only; no cipher or security result.'}
            status,lab=_post(address,self.base+'lab',lab_body)
            self.assertEqual(status,200);self.assertFalse(lab['mastery_updated'])
            self.assertEqual(_post(address,self.base+'lab',lab_body),(status,lab))
            submission={key:value for key,value in lab_body.items() if key!='prediction'}
            submission.update(submission_id='synthetic-app-http-submission',reflection='The known fixtures reproduce structure; security and learner transfer remain unmeasured.')
            status,payload=_post(address,self.base+'submit-lab',submission)
            self.assertEqual(status,200);self.assertEqual(payload['status'],'pending_review');self.assertFalse(payload['mastery_updated'])
            for raw in (b'{"query":"'+RAW_MARKER.encode()+b'",}',b'{"query":NaN}',b' ' * 131073,
                        ('{"'+TOKEN_MARKER+'":1,"'+TOKEN_MARKER+'":2}').encode()):
                status,payload=_post(address,self.base+'evidence',raw)
                self.assertIn(status,(400,413));self.assert_redacted(payload)
            for content_length in (TOKEN_MARKER,'-1','0','131073'):
                status,payload=_post(address,self.base+'evidence',{**self.body,'query':'placeholder'},
                    headers={'Content-Length':content_length})
                self.assertEqual(status,400);self.assert_redacted(payload)
            status,payload=_post(address,self.base+'evidence',{**self.body,'query':'placeholder','actor':RAW_MARKER})
            self.assertEqual(status,400);self.assert_redacted(payload)
            status,payload=_post(address,self.base+'evidence',{**self.body,'query':'placeholder'},token=TOKEN_MARKER)
            self.assertEqual(status,401);self.assert_redacted(payload)
            status,payload=_post(address,self.base+'evidence',{**self.body,'query':'placeholder'},headers={'Origin':'https://foreign.example'})
            self.assertEqual(status,403);self.assert_redacted(payload)

    def test_actual_app_research_routes_disabled_without_injected_adapter(self):
        with _loopback(self,_handler(None,actual_app=True)) as address:
            for action in ('sources','evidence','lab','submit-lab'):
                status,payload=_post(address,self.base+action,{'synthetic':TOKEN_MARKER})
                self.assertEqual(status,503);self.assert_redacted(payload)


if __name__=='__main__':unittest.main()
