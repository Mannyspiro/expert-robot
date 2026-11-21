"""Live synthetic context/worker/process integration, not a native LLM review.

Executed only by an exact-source authorized host controller. No production state,
private chat archive, new permissions or external provider is used. All artifacts
are in temporary registry/queue/ledger stores. Parent-only canaries are synthetic.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import uuid
from unittest.mock import patch
from merlin.project_registry import MerlinRegistry
from merlin.branch_research import Branch, digest
from merlin.branch_registry import RegistryBranchSession
from merlin.branch_task_recovery import task_path
from merlin.packet_process import FixedPacketExecutor, packet_executor_identity
from merlin.hermes_process import ProcessLimits
from merlin.hermes_systemd import SystemdFixedPythonProcess, _show
from merlin.event_outbox import MerlinEventOutbox
from merlin.hermes_worker import HermesWorker, HERMES_TASK_TOPIC
from merlin.hermes_stage_handlers import build_hermes_stage_handlers
from merlin.research_evidence import ResearchEvidenceRecorder
from merlin.hypothesis_ledger import HypothesisLedger
from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.review_context import ReviewContext
from dot_ai_os.bridge import DotContextBridge, canonical
from dot_ai_os.research_protocol import research_episode_demo, store_research_record, _sealed, _validated_plan

PROGRAM = '''import hashlib,json,sys
raw=sys.stdin.buffer.read(65537)
assert len(raw)<=65536
p=json.loads(raw)
assert p['schema']=='merlin-goldfish-packet/1'
print(json.dumps({'packet_sha256':hashlib.sha256(raw).hexdigest(),
 'roles':[d['role'] for d in p['documents']],
 'text_hashes':[hashlib.sha256(d['text'].encode()).hexdigest() for d in p['documents']],
 'parent_transcript_supplied':p['parent_transcript_supplied'],'model_review_performed':False}))
'''
CHECKER = '''def check(raw, receipt):
    p=json.loads(raw);v=json.loads(receipt['stdout'])
    good=(v['packet_sha256']==hashlib.sha256(raw).hexdigest()
      and v['roles']==['persona','target','standard','source']
      and v['text_hashes']==[hashlib.sha256(d['text'].encode()).hexdigest() for d in p['documents']]
      and v['parent_transcript_supplied'] is False and v['model_review_performed'] is False)
    return {'passed':good,'detail':'Exact synthetic context transport; no model review performed'}
'''
exec(compile(CHECKER, 'review-packet-checker', 'exec'))
CHECKER_SHA = hashlib.sha256(CHECKER.encode()).hexdigest()


class Fixture:
    def __init__(self, root, source_commit, *, code=PROGRAM):
        self.root=Path(root);self.registry=MerlinRegistry(self.root/'registry')
        self.bridge=DotContextBridge(self.registry,project_id='test',namespaces=('merlin',));self.bridge.initialize()
        self.allowed=True;self.process_allowed=True;self.units=set();self.launches=0
        self.contexts=ReviewContext(self.bridge,authorize=lambda *_:self.allowed)
        self.canary='PARENT_ONLY_'+uuid.uuid4().hex
        pin=self.bridge.ingest(namespace='merlin',source_id='synthetic-history',title='Continuity fixture',
            content=('Continuity '+self.canary).encode(),source_url='https://example.org/synthetic-history',
            source_version='fixture-1',epistemic='historical_report',captured_at='2026-11-20T15:00:00Z')
        self.pin={k:pin[k] for k in ('record_ref','source_ref')}
        self.bridge.save_handoff('parent',summary='Builder-only '+self.canary,next_action='Measure exact transport',
            source_refs=[self.pin['source_ref']])
        def put(path,text):
            self.registry.put_artifact('test',path,text.encode(),'text/plain');return self.registry.artifact_ref('test',path)
        persona=put('reviewers/persona.md','# Reviewer\nChallenge unstated assumptions.\n')
        target=put('design/spec.md','# Design\nUse exact source identities.\n')
        standard=put('standards/review.md','# Standard\nRecord missing assumptions.\n')
        source=put('sources/reference.md','# Reference\nReviews do not authorize deployment.\n')
        self.elephant_args=dict(source_commit=source_commit,query='continuity',pinned_records=[self.pin],
            known_gaps=['Synthetic-only run; not account-wide chat history'])
        self.elephant=self.contexts.elephant('parent',**self.elephant_args)
        self.packet=self.contexts.goldfish(source_commit=source_commit,persona_ref=persona,target_ref=target,
            standard_refs=[standard],source_refs=[source]);self.input_ref=self.packet['packet_ref']
        self.frame=research_episode_demo({})['research_plan'];self.frame['source_commit']=source_commit
        self.frame=_sealed({k:v for k,v in self.frame.items() if k!='record_sha256'});_validated_plan(self.frame)
        self.frame_ref=store_research_record(self.registry,'test',self.frame)['artifact_ref']
        program=self.root/'fixed.py';program.write_text(code)
        self.process=SystemdFixedPythonProcess(program,hashlib.sha256(program.read_bytes()).hexdigest())
        self.limits=ProcessLimits(cpu_seconds=1,wall_seconds=2,output_bytes=8192)
        identity=packet_executor_identity(program_sha256=self.process.sha256,checker_sha256=CHECKER_SHA,
            input_ref=self.input_ref,limits=self.limits,tasks_max=self.process.tasks_max)
        self.session=RegistryBranchSession(self.registry,project_id='test',session_id='context-session',
            branches=(Branch('a','Packet transport',2),Branch('b','Dependent',1,('a',))),source_commit=source_commit,
            research_plan_ref=self.frame_ref,principal='synthetic-host',executor_id='fixed-review-packet',executor_sha256=identity,
            frame_validator=_validated_plan,approval=lambda _:self.allowed,lease=lambda _:True)
        def authority(data):
            unit=data['process_policy'].get('unit')
            if unit:self.units.add(unit)
            return self.process_allowed
        self.executor=FixedPacketExecutor(self.session,self.process,input_ref=self.input_ref,limits=self.limits,
            checker=check,checker_sha256=CHECKER_SHA,authorize=authority)
        self.ledger=HypothesisLedger(self.root/'hypotheses.sqlite3');self.ledger.create('H-context','Synthetic packet transport')
        self.graph=MerlinKnowledgeGraph(self.root/'graph.sqlite3')
        self.outbox=MerlinEventOutbox(self.root/'outbox.sqlite3')
        self.recorder=ResearchEvidenceRecorder(self.registry,self.ledger,self.graph)
        self.source_commit=source_commit
        self.handlers=self.make_handlers(self.executor)
        self.worker=self.make_worker()

    def make_handlers(self, executor):
        def unused(*_):raise AssertionError('unselected stage')
        return build_hermes_stage_handlers(evidence_recorder=self.recorder,project_id='test',
            research_executor=executor,numerical_experiment_executor=unused,proof_search_executor=unused,
            artifact_verifier=None,repository='Mannyspiro/expert-robot',commit_sha=self.source_commit,requester_id='synthetic-host')

    def make_worker(self):
        return HermesWorker(self.outbox,handlers=self.handlers,approval_validator=lambda *_:self.allowed,
            lease_validator=lambda *_:True,worker_id='context-drill',retry_delay_seconds=0,
            artifact_ref_validator=lambda ref:self.registry.resolve_artifact_ref(ref)['verified'])

    def enqueue(self, task_id='tick-1', key='queue-1'):
        task={'schema':'merlin-research-task/2','task_id':task_id,'hypothesis_id':'H-context','objective':'Check synthetic packet transport',
            'stage':'research','approval_ref':'synthetic-approval','lease_ref':'synthetic-lease',
            'resource_budget':{'cpu_cores':1,'memory_bytes':128*1024*1024,'max_wall_seconds':20,'compute_budget_units':1},
            'artifact_refs':[deepcopy(self.frame_ref),deepcopy(self.input_ref)],'authority':'bounded_execution_only','promotion_authority':False}
        return self.outbox.enqueue(key,HERMES_TASK_TOPIC,task)

    def cleanup(self):
        result={}
        for unit in sorted(self.units):
            state=_show(unit);result[unit]=state
            assert state.get('LoadState')=='not-found' or state.get('ActiveState') in {'inactive','failed'},state
        return result


def run(output, *, source_commit):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    report={'schema':'merlin-live-review-context/1','source_commit':source_commit,'cases':[],
        'private_context_used':False,'actual_native_model_review_performed':False,
        'production_service_modified':False,'permissions_modified':False,'qualification':False,'promotion_authority':False}
    def case(name, procedure, code=PROGRAM):
        row={'name':name,'passed':False}
        with tempfile.TemporaryDirectory(prefix='merlin-egm-fixture-',dir='/run') as root:
            f=None
            try:
                f=Fixture(root,source_commit,code=code);row.update(procedure(f));row['cleanup']=f.cleanup();row['passed']=True
            except Exception as exc:
                row.update(error_class=type(exc).__name__,error=str(exc)[:1500])
                if f is not None:row['cleanup']=f.cleanup()
            report['cases'].append(row)
            (output/'context-worker-report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    def completion(f):
        raw=f.registry.read_artifact_ref(f.input_ref)['content']
        assert f.canary in canonical(f.elephant['packet']).decode() and f.canary not in raw.decode()
        resumed=ReviewContext(DotContextBridge(MerlinRegistry(f.registry.root),project_id='test',namespaces=('merlin',)),authorize=lambda *_:True)
        assert resumed.elephant('parent',**f.elephant_args)==f.elephant
        f.enqueue();first=f.worker.run_once();assert first['status']=='completed',first
        process=f.session._read('processes/a.json')[0]
        assert f.canary not in process['process']['stdout']
        assert json.loads(process['process']['stdout'])['packet_sha256']==f.input_ref['sha256']
        f.enqueue(key='duplicate');second=f.make_worker().run_once()
        assert second['status']=='completed' and first['receipt']==second['receipt'] and len(f.units)==1
        blocked=f.contexts.blocked_review(f.input_ref)['packet'];assert blocked['model_review_performed'] is False
        assert blocked['status']=='blocked_missing_fresh_context_runtime'
        assert first['receipt']['result']['cace_verification']['verification_status']=='blocked_missing_credentials'
        return {'continuity_restart_exact':True,'parent_canary_excluded':True,'process_receipt':process,
            'duplicate_same_receipt':True,'process_launches':len(f.units),'review':blocked}
    case('context_restart_actual_worker_process_and_duplicate_replay',completion)
    def ack(f):
        f.enqueue();saved=[]
        def fail(*args,**kwargs):saved.append(deepcopy(kwargs['result']));raise OSError('synthetic acknowledgement loss')
        with patch.object(f.outbox,'acknowledge',side_effect=fail):assert f.worker.run_once()['status']=='pending'
        replay=f.make_worker().run_once();assert replay['status']=='completed' and replay['receipt']==saved[0]
        assert len(f.units)==1 and f.session.status()['completed']==1
        return {'ack_loss_replay_exact':True,'process_launches':1,'process_receipt':f.session._read('processes/a.json')[0]}
    case('acknowledgement_loss_after_real_process',ack)
    def completed_process_recovery(f):
        f.enqueue()
        with patch.object(f.executor,'checker',side_effect=OSError('synthetic interruption after durable process receipt')):
            interrupted=f.worker.run_once()
        assert interrupted['status']=='pending' and len(f.units)==1,interrupted
        assert f.session.status()['reconciliation_required']=='a'
        process=f.session._read('processes/a.json');failure=f.session._read('failures/a.json')
        assert process is not None and failure is not None
        assert process[0]['process']['status']=='completed'
        automatic=f.make_worker().run_once()
        assert automatic['status']!='completed' and len(f.units)==1,automatic
        body={'schema':'merlin-packet-recovery-decision/1',
            'request_ref':f.registry.artifact_ref('test',task_path('tick-1')+'request.json'),
            'intent_ref':f.session._read('intents/a.json')[1],'process_ref':process[1],
            'expected_state_sha256':digest(f.session.status()),'source_commit':f.source_commit,
            'session_id':f.session.session_id,'executor_sha256':f.executor.identity,
            'input_ref':f.input_ref,'checker_sha256':CHECKER_SHA,'action':'check_completed_process_only',
            'checker_replay_authorized':True,'process_reexecution_authorized':False,
            'reviewer_id':'synthetic-host-reviewer','reason':'Authorize one exact checker replay in isolated fixture',
            'authority':'reconcile_only','qualification':False,'promotion_authority':False}
        f.registry.put_artifact('test','recovery-decisions/packet.json',canonical(body),'application/json')
        decision_ref=f.registry.artifact_ref('test','recovery-decisions/packet.json')
        f.executor.recovery_authorizer=lambda ref,decision:(canonical(ref)==canonical(decision_ref)
            and canonical(decision)==canonical(body))
        handler=lambda task,ctx:f.executor.reconcile(task,ctx,decision_ref=decision_ref)
        f.handlers=f.make_handlers(handler)
        with patch.object(f.process,'run',side_effect=AssertionError('recovery must not relaunch')):
            recovered=f.make_worker().run_once()
        assert recovered['status']=='completed' and len(f.units)==1,recovered
        assert f.session.status()['completed']==1 and f.session.status()['reconciliation_required'] is None
        assert f.session._read('processes/a.json')==process and f.session._read('failures/a.json')==failure
        recovery_ref=recovered['receipt']['result']['metadata']['task_recovery_ref']
        recovery=json.loads(f.registry.read_artifact_ref(recovery_ref)['content'])
        assert recovery['process_reexecuted'] is False and recovery['evaluator_reexecuted'] is False
        assert recovery['process_ref']==process[1] and recovery['decision_ref']==decision_ref
        assert recovery['outcome_ref']==f.session._read('outcomes/a.json')[1]
        check_result=json.loads(f.registry.read_artifact_ref(recovery['checker_result_ref'])['content'])
        assert check_result['check']['passed'] is True and check_result['process_ref']==process[1]
        f.handlers=f.make_handlers(f.executor);f.enqueue(key='recovered-duplicate')
        with patch.object(f.process,'run',side_effect=AssertionError('duplicate must not relaunch')):
            replay=f.make_worker().run_once()
        assert replay['status']=='completed' and replay['receipt']==recovered['receipt'] and len(f.units)==1
        assert recovered['receipt']['result']['cace_verification']['verification_status']=='blocked_missing_credentials'
        return {'ordinary_retry_blocked':True,'checker_only_recovery_completed':True,
            'process_launches':1,'duplicate_fresh_worker_receipt_exact':True,
            'original_failure_ref':failure[1],'process_ref':process[1],'process_receipt':process[0],
            'recovery_ref':recovery_ref,'recovery':recovery,'checker_result':check_result,
            'actual_native_model_review_performed':False}
    case('completed_process_checker_recovery_without_relaunch',completed_process_recovery)
    def cancel(f):
        event=f.enqueue();original=f.process.run
        def invoke(raw,**kw):
            auth=kw['authorize'];start=time.monotonic()
            def revoke(policy):
                result=auth(policy)
                if time.monotonic()-start>.5:f.outbox.cancel(event['event_id'],'synthetic-operator')
                return result
            kw['authorize']=revoke;return original(raw,**kw)
        with patch.object(f.process,'run',side_effect=invoke):result=f.worker.run_once()
        assert result['status']=='cancelled',result
        assert f.session.status()['reconciliation_required']=='a' and f.session.status()['completed']==0
        assert len(f.units)==1
        f.enqueue(task_id='next',key='next');assert f.worker.run_once()['status']!='completed'
        assert len(f.units)==1
        return {'task_status':'cancelled','ambiguous_intent_blocks_successor':True,'process_launches':1}
    case('actual_cancellation_stops_process_and_fences_successor',cancel,code='import time\ntime.sleep(20)\n')
    def revoke(f):
        f.enqueue();f.process_allowed=1
        result=f.worker.run_once();assert result['status']!='completed' and not f.units
        assert f.session.status()['reconciliation_required']=='a'
        return {'truthy_authority_rejected':True,'process_launches':0,'reconciliation_required':'a'}
    case('non_boolean_host_authority_cannot_start_process',revoke)
    def wrong(f):
        f.enqueue();result=f.worker.run_once();assert result['status']=='completed',result
        assert f.session.status()['branches']==[{'id':'a','status':'failed_local_check'},{'id':'b','status':'waiting'}]
        f.enqueue(task_id='next',key='next');assert f.worker.run_once()['status']=='completed' and len(f.units)==1
        return {'failed_local_check_blocks_dependency':True,'process_launches':1,'process_receipt':f.session._read('processes/a.json')[0]}
    bad=PROGRAM.replace("'parent_transcript_supplied':p['parent_transcript_supplied']", "'parent_transcript_supplied':True")
    case('wrong_output_cannot_pass_or_advance_dependency',wrong,code=bad)
    report.update(status='succeeded' if all(r['passed'] for r in report['cases']) else 'failed',
        tests=len(report['cases']),passed=sum(r['passed'] for r in report['cases']))
    (output/'context-worker-report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    return report
