#!/usr/bin/env python3
"""Opt-in real CLI/OIDC acceptance using ephemeral loopback RS256 fixtures.

Requires separately installed cryptography and an external official PyJWT2.15.1
source checkout; no package code is vendored or installed by this script. Keys
and signed credentials stay in memory, never argv/environment/files/receipts.
This proves local synthetic acceptance, not institutional issuer/tenant readiness.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
from http import client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

PYJWT_REVISION='7d5ef55e42ce42221f58dc49943e92ccad1fa66a'
PYJWT_VERSION='2.15.1'
REPO=Path(__file__).resolve().parents[2]
SOURCE_PATHS=['python/merlin/app.py','python/merlin/identity.py','python/merlin/learning_research_config.py',
              'python/merlin/learning_evidence.py','python/merlin/learning_evidence_eval.py']


def _sha(raw):return hashlib.sha256(raw).hexdigest()


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def _tree(root):
    entries={}
    for path in sorted((root/'jwt').rglob('*.py')):
        if path.is_symlink() or not path.is_file():raise ValueError('auth source must contain regular files')
        raw=path.read_bytes()
        if len(raw)>1024*1024 or len(entries)>=64:raise ValueError('auth source bounds exceeded')
        entries[path.relative_to(root).as_posix()]=_sha(raw)
    if not entries:raise ValueError('auth package source missing')
    return {'sha256':_sha(_canonical(entries)),'python_files':len(entries)}


def _request(port,method,path,payload=None,token=None):
    body=None if payload is None else _canonical(payload)
    headers={} if body is None else {'Content-Type':'application/json','Content-Length':str(len(body))}
    if token is not None:headers['Authorization']='Bearer '+token
    connection=client.HTTPConnection('127.0.0.1',port,timeout=3)
    try:
        connection.request(method,path,body,headers=headers)
        response=connection.getresponse();raw=response.read(262145)
        if len(raw)>262144:raise ValueError('response ceiling exceeded')
        return response.status,json.loads(raw)
    finally:connection.close()


def _port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));return listener.getsockname()[1]


@contextmanager
def _jwks(document):
    raw=_canonical(document)
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path!='/jwks':self.send_error(404);return
            requests.append(True)
            self.send_response(200);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.01},daemon=True);thread.start()
    try:yield server.server_address[1],requests
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
        if thread.is_alive():raise RuntimeError('fixture JWKS server failed to stop')


@contextmanager
def _normal_cli(root,environment,port,logs):
    """Literal normal module invocation, no injected application resolver/API."""
    path=root/'app-output.log'
    with path.open('wb') as log:
        process=subprocess.Popen([sys.executable,'-B','-u','-m','merlin.app','--port',str(port),
            '--db',str(root/'events.sqlite3')],cwd=str(root),env=environment,stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+30
            while True:
                if process.poll() is not None:raise RuntimeError('normal CLI exited before readiness')
                try:
                    status,health=_request(port,'GET','/health')
                    if status!=200 or health.get('ok') is not True or health.get('service')!='merlin':
                        raise RuntimeError('unexpected normal CLI health contract')
                    break
                except ConnectionRefusedError:
                    if time.monotonic()>=deadline:raise RuntimeError('normal CLI readiness deadline exceeded')
                    time.sleep(.05)
            yield process
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait(timeout=5)
                    raise RuntimeError('normal CLI SIGTERM deadline exceeded')
            log.flush()
            logs.append({'sha256':_sha(path.read_bytes()),'bytes':path.stat().st_size,'exit_code':process.returncode})
        if process.returncode!=0:raise RuntimeError('normal CLI did not exit cleanly')


def validate(auth_pythonpath,source_commit):
    if not isinstance(source_commit,str) or re.fullmatch(r'[0-9a-f]{40}',source_commit) is None:
        raise ValueError('host source commit must be full lowercase Git SHA')
    auth=Path(auth_pythonpath).resolve(strict=True)
    dependency_identity=_tree(auth)
    source_identity={p:_sha((REPO/p).read_bytes()) for p in SOURCE_PATHS}
    sys.path[:0]=[str(auth),str(REPO/'python')]
    import jwt
    import cryptography
    from cryptography.hazmat.primitives.asymmetric import rsa
    from merlin.learning_evidence_eval import _setup_demo,grade_evidence_response,FIXTURE_SHA256
    if jwt.__version__!=PYJWT_VERSION or Path(jwt.__file__).resolve().parent!=auth/'jwt':
        raise ValueError('exact external pinned PyJWT profile required')
    # Key objects are intentionally never serialized to a file or receipt.
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    wrong_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    public=jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(),as_dict=True)
    public.update(kid='synthetic-ephemeral-rs256',alg='RS256',use='sig')
    outcomes=[];logs=[]
    with tempfile.TemporaryDirectory(prefix='merlin-cli-oidc-') as temporary:
        root=Path(temporary)
        fixture,platform,registry,_,_,teacher,learner,scope,pins,frozen=_setup_demo(root,source_commit)
        expected={'tenant_id':learner.tenant_id,'project_id':'synthetic-learning-evidence',**scope}
        body={key:scope[key] for key in ('course_version','manifest_sha256')}
        base='/api/learning/courses/'+scope['course_id']+'/research/'
        with _jwks({'keys':[public]}) as (issuer_port,jwks_requests):
            issuer='http://127.0.0.1:'+str(issuer_port)+'/synthetic-issuer'
            audience='synthetic-merlin-cli-acceptance'
            environment={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'LANG':'C.UTF-8',
                'PYTHONPATH':os.pathsep.join([str(auth),str(REPO/'python')]),
                'PYTHONNOUSERSITE':'1','PYTHONSAFEPATH':'1','PYTHONDONTWRITEBYTECODE':'1',
                'MERLIN_DB_PATH':str(root/'events.sqlite3'),'MERLIN_LEARNING_DB_PATH':str(root/'learning.sqlite3'),
                'MERLIN_LEARNER_DB_PATH':str(root/'learning.sqlite3'),'MERLIN_MEMORY_DB_PATH':str(root/'memory.sqlite3'),
                'MERLIN_REGISTRY_ROOT':str(root/'registry'),
                'MERLIN_LEARNING_RESEARCH_TENANT_PROJECTS':json.dumps({learner.tenant_id:'synthetic-learning-evidence'}),
                'MERLIN_OIDC_ISSUER':issuer,'MERLIN_OIDC_AUDIENCE':audience,
                'MERLIN_OIDC_JWKS_URL':'http://127.0.0.1:'+str(issuer_port)+'/jwks',
                'MERLIN_OIDC_ALLOWED_ALGORITHMS':'RS256','MERLIN_OIDC_LEEWAY_SECONDS':'0',
                'MERLIN_OIDC_JWKS_TIMEOUT_SECONDS':'3','MERLIN_OIDC_MAX_TOKEN_LIFETIME_SECONDS':'300'}
            def signed(actor,**changes):
                now=int(time.time())
                claims={'iss':issuer,'aud':audience,'sub':actor.actor_id,'tenant_id':actor.tenant_id,
                    'role':actor.role,'iat':now,'nbf':now-1,'exp':now+120,'jti':'synthetic-ephemeral-credential'}
                claims.update(changes)
                return jwt.encode(claims,key,algorithm='RS256',headers={'kid':public['kid']})
            learner_token=signed(learner);teacher_token=signed(teacher)
            port=_port();first=[]
            with _normal_cli(root,environment,port,logs):
                for case in fixture['cases']:
                    status,response=_request(port,'POST',base+'evidence',{**body,'query':case['query']},learner_token)
                    grade=grade_evidence_response(case['case_id'],response,pinned_sources=pins,
                        expected_binding=expected,expected_source_manifest_ref=frozen['source_manifest_ref'])
                    if status!=200 or not grade['passed']:raise RuntimeError('independent byte/scope oracle failed')
                    first.append(response);outcomes.append({'case_id':case['case_id'],'status':status,'passed':True,
                        'response_sha256':_sha(_canonical(response))})
                negative=[('missing-credential',None,401),('wrong-audience',signed(learner,aud='wrong-audience'),401),
                    ('wrong-issuer',signed(learner,iss=issuer+'/wrong'),401),
                    ('expired',signed(learner,iat=int(time.time())-180,exp=int(time.time())-60),401),
                    ('foreign-tenant',signed(learner,tenant_id='unprovisioned-synthetic-tenant'),403)]
                claims=jwt.decode(learner_token,options={'verify_signature':False})
                negative.append(('wrong-signature',jwt.encode(claims,wrong_key,algorithm='RS256',headers={'kid':public['kid']}),401))
                negative.append(('unapproved-algorithm',jwt.encode(claims,key='',algorithm='none',headers={'kid':public['kid']}),401))
                for case_id,credential,expected_status in negative:
                    status,response=_request(port,'POST',base+'evidence',{**body,'query':'placeholder'},credential)
                    if status!=expected_status or 'detail' in response:raise RuntimeError('negative authentication case failed')
                    if credential and credential in json.dumps(response):raise RuntimeError('credential leaked into HTTP error')
                    outcomes.append({'case_id':case_id,'status':status,'passed':True,'response_sha256':_sha(_canonical(response))})
                curation={**body,'sources':[{'resource_id':source['resource_id'],**pins[source['resource_id']],
                    'review_note':'Original synthetic CC0 text; fixture scope and source metadata reviewed.'} for source in fixture['sources']],
                    'conflicts':fixture['conflicts']}
                status,response=_request(port,'POST',base+'sources',curation,teacher_token)
                if status!=200 or response['source_manifest_ref']!=frozen['source_manifest_ref']:raise RuntimeError('curator scope failed')
                outcomes.append({'case_id':'signed-curator-replay','status':status,'passed':True,'response_sha256':_sha(_canonical(response))})
                status,response=_request(port,'POST',base+'evidence',{**body,'query':'placeholder','actor':{'role':'tenant_admin'}},learner_token)
                if status!=400:raise RuntimeError('body identity override accepted')
                outcomes.append({'case_id':'body-identity-rejected','status':status,'passed':True,'response_sha256':_sha(_canonical(response))})
                status,response=_request(port,'POST',base+'lab',{**body,'lesson_id':'titan-structural-lab','run_id':'disabled',
                    'prediction':'No lab was configured.'},learner_token)
                if status!=503:raise RuntimeError('evidence configuration unexpectedly enabled lab')
                outcomes.append({'case_id':'lab-remains-disabled','status':status,'passed':True,'response_sha256':_sha(_canonical(response))})
            with _normal_cli(root,environment,port,logs):
                for case,previous in zip(fixture['cases'],first):
                    status,response=_request(port,'POST',base+'evidence',{**body,'query':case['query']},learner_token)
                    if status!=200 or _canonical(response)!=_canonical(previous):raise RuntimeError('CLI restart changed pinned evidence')
                outcomes.append({'case_id':'normal-cli-restart','status':200,'passed':True})
            if not jwks_requests:raise RuntimeError('JWKS transport was not exercised')
            jwks_count=len(jwks_requests)
        with sqlite3.connect(root/'learning.sqlite3') as db:
            if db.execute('SELECT COUNT(*) FROM learner_attempts').fetchone()[0]!=0:raise RuntimeError('unexpected learner score')
            if db.execute('SELECT COUNT(*) FROM learning_submissions').fetchone()[0]!=0:raise RuntimeError('unexpected assessment submission')
    if source_identity!={p:_sha((REPO/p).read_bytes()) for p in SOURCE_PATHS}:
        raise RuntimeError('runtime source changed during acceptance')
    return {'schema':'merlin-normal-cli-oidc-acceptance/1','status':'passed','fixture_class':'ephemeral_loopback_signed_rs256',
        'host_source_commit':source_commit,'runtime_source_sha256':source_identity,
        'script_sha256':_sha(Path(__file__).read_bytes()),'fixture_sha256':FIXTURE_SHA256,
        'auth_dependency':{'project':'jpadilla/pyjwt','revision':PYJWT_REVISION,'version':jwt.__version__,
            'source_tree':dependency_identity,'cryptography_version':cryptography.__version__},
        'python_version':sys.version.split()[0],'command_profile':'python -B -u -m merlin.app',
        'case_count':len(outcomes),'passed':len(outcomes),'cases':outcomes,'jwks_get_count':jwks_count,
        'process_logs':logs,'ephemeral_credentials_persisted':False,'synthetic_only':True,
        'institutional_identity_attested':False,'mastery_updated':False,'qualification':False,'promotion_authority':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--auth-pythonpath',required=True,help='External pinned official PyJWT2.15.1 source root')
    parser.add_argument('--source-commit',required=True,help='Host provenance commit; modified runtime file hashes are also recorded')
    parser.add_argument('--output',type=Path,help='Write a non-secret machine-readable receipt')
    args=parser.parse_args()
    try:receipt=validate(args.auth_pythonpath,args.source_commit)
    except Exception as exc:
        # Deliberately exclude exception messages, commands, headers and log text.
        receipt={'schema':'merlin-normal-cli-oidc-acceptance/1','status':'failed','error_class':type(exc).__name__,
            'host_source_commit':args.source_commit if re.fullmatch(r'[0-9a-f]{40}',args.source_commit) else None,
            'script_sha256':_sha(Path(__file__).read_bytes()),
            'runtime_source_sha256':{p:_sha((REPO/p).read_bytes()) for p in SOURCE_PATHS if (REPO/p).is_file()},
            'fixture_sha256':_sha((REPO/'tests/fixtures/learning-evidence-eval-v1.json').read_bytes()),
            'synthetic_only':True,'ephemeral_credentials_persisted':False,'qualification':False,'promotion_authority':False}
    raw=json.dumps(receipt,sort_keys=True,indent=2)+'\n'
    if args.output:
        with args.output.open('x') as stream:stream.write(raw)
    print(raw,end='')
    return 0 if receipt['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
