"""Bounded live cgroup fixtures, run only by an approved exact-source host controller.

Uses temporary merlin-fixed-UUID services and synthetic files. No installs,
production service changes, grant changes or real private registry access.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from merlin.hermes_process import ProcessLimits
from merlin.hermes_systemd import SystemdFixedPythonProcess, _show


def stopped(pid):
    path=Path('/proc')/str(pid)/'stat'
    for _ in range(100):
        if not path.exists(): return
        try:
            if path.read_text().split(') ',1)[1].split()[0] in ('Z','X'): return
        except FileNotFoundError: return
        time.sleep(.01)
    raise AssertionError('synthetic descendant still running')


def context():
    return SimpleNamespace(resource_budget={'cpu_cores':1,'memory_bytes':64*1024*1024,
        'max_wall_seconds':10,'compute_budget_units':1},deadline_epoch=time.time()+15,
        check_cancelled=lambda:None)


def run(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    report={'schema':'merlin-live-cgroup-drill/1','host_uid':os.geteuid(),'cases':[],
        'production_service_modified':False,'private_state_accessed':False,
        'permissions_modified':False,'qualification':False,'promotion_authority':False}
    def save():
        (output/'cgroup-report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if not SystemdFixedPythonProcess.available():
        report['status']='blocked_host_manager_unavailable';save();return report
    report['systemd_version']=subprocess.run(['/usr/bin/systemctl','--version'],capture_output=True,text=True,timeout=5).stdout.splitlines()[0]
    with tempfile.TemporaryDirectory(prefix='merlin-cgroup-drill-') as temp:
        root=Path(temp)
        def case(name,code,check,*,wall=3,tasks=8):
            path=root/(name+'.py');path.write_text(code)
            row={'name':name,'passed':False}
            try:
                runner=SystemdFixedPythonProcess(path,hashlib.sha256(path.read_bytes()).hexdigest(),tasks_max=tasks)
                receipt=runner.run(b'{"n":10}',limits=ProcessLimits(cpu_seconds=1,wall_seconds=wall),context=context(),authorize=lambda _:True)
                row['receipt']=receipt
                if receipt['kernel_setup'] is None: raise AssertionError('kernel setup missing')
                check(receipt);row['passed']=True
            except Exception as exc:
                row.update(error_class=type(exc).__name__,error=str(exc)[:1500])
            report['cases'].append(row);save()
        def complete(r):
            if r['status']!='completed': raise AssertionError('fixed program did not complete')
        def arithmetic(r):
            complete(r);assert json.loads(r['stdout'])['sum']==55
            assert r['kernel_setup']['uid']!=0
        case('fixed_program_and_actual_kernel_limits',
            'import json,sys\nx=json.load(sys.stdin)\nprint(json.dumps({"sum":sum(range(x["n"]+1))}))\n',arithmetic)
        def memory(r):
            assert r['status']=='failed',r['status']
            assert r['manager_result'].get('Result')=='oom-kill',r['manager_result']
            assert r['kernel_setup']['controllers']['memory.max']==str(64*1024*1024)
            assert r['elapsed_seconds']<7
        case('aggregate_memory_limit',
            'import subprocess,sys,time\nps=[subprocess.Popen([sys.executable,"-I","-B","-S","-c","import time; x=bytearray(48*1024*1024); time.sleep(20)"]) for _ in range(2)]\nprint("children="+str([p.pid for p in ps]),flush=True)\ntime.sleep(20)\n',memory)
        def cpulimit(r):
            assert r['status']=='failed'
            assert r['manager_result'].get('Result')=='signal',r['manager_result']
            assert r['manager_result'].get('ExecMainStatus') in {'9','24'},r['manager_result']
            assert r['elapsed_seconds']<6
        case('cpu_time_limit','while True: pass\n',cpulimit,wall=5)
        def taskcap(r):
            complete(r);obj=json.loads(r['stdout']);assert obj['denied']>=1,obj
            for pid in obj['pids']:stopped(pid)
        case('tasks_max_fork_denial',
            'import subprocess,sys,json\nps=[];denied=0\nfor _ in range(8):\n try: ps.append(subprocess.Popen([sys.executable,"-I","-B","-S","-c","import time;time.sleep(20)"]))\n except OSError: denied+=1\nprint(json.dumps({"denied":denied,"pids":[p.pid for p in ps]}),flush=True)\n',taskcap,tasks=3)
        def detached(r):
            complete(r);stopped(json.loads(r['stdout'])['detached_pid'])
        case('detached_descendant_cleanup',
            'import subprocess,sys,json\np=subprocess.Popen([sys.executable,"-I","-B","-S","-c","import time;time.sleep(20)"],start_new_session=True)\nprint(json.dumps({"detached_pid":p.pid}),flush=True)\n',detached)
        def wall(r):
            assert r['status']=='failed'
            assert r['manager_result'].get('Result')=='timeout',r['manager_result']
            assert r['elapsed_seconds']<6;stopped(r['kernel_setup']['pid'])
        case('manager_wall_deadline','import time\ntime.sleep(20)\n',wall,wall=.4)
        def network(r):
            complete(r);assert json.loads(r['stdout'])['blocked'] is True
        case('inet_socket_creation_denied',
            'import socket,json\ntry:\n s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.close();blocked=False\nexcept OSError: blocked=True\nprint(json.dumps({"blocked":blocked}))\n',network)
        path=root/'cancel.py';path.write_text('import time\ntime.sleep(20)\n')
        captured={};started=time.monotonic()
        def revoke(policy):
            captured['unit']=policy['unit'];return time.monotonic()-started<.5
        row={'name':'revoked_authorization_stops_unit','passed':False}
        try:
            SystemdFixedPythonProcess(path,hashlib.sha256(path.read_bytes()).hexdigest()).run(b'{}',
                limits=ProcessLimits(cpu_seconds=1,wall_seconds=3),context=context(),authorize=revoke)
            raise AssertionError('revoked authorization accepted')
        except PermissionError:
            state=_show(captured['unit']);row['cleanup']=state
            row['passed']=state.get('LoadState')=='not-found' or state.get('ActiveState') in {'inactive','failed'}
        except Exception as exc:row.update(error_class=type(exc).__name__,error=str(exc)[:1500])
        report['cases'].append(row)
    report.update(status='succeeded' if all(c['passed'] for c in report['cases']) else 'failed',
        tests=len(report['cases']),passed=sum(c['passed'] for c in report['cases']))
    save();return report


if __name__=='__main__':
    result=run(sys.argv[1]);print(json.dumps({k:v for k,v in result.items() if k!='cases'}),flush=True)
    sys.exit(0 if result['status']=='succeeded' else 1)
