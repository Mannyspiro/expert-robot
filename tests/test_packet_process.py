"""Fixed packet boundaries using actual Hermes stores; process execution is mocked.

The OCI integration drill separately exercises the actual systemd backend.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import unittest
import test_branch_worker as worker_fixture
from merlin.packet_process import FixedPacketExecutor, packet_executor_identity
from merlin.branch_registry import RegistryBranchSession
from merlin.hermes_process import ProcessLimits
from merlin.hermes_systemd import SystemdFixedPythonProcess


class PacketProcessTests(unittest.TestCase):
    def setUp(self):
        self.fixture = worker_fixture.BranchWorkerTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        f = self.fixture; p = f.root/'program.py'; p.write_text('print("ok")\n')
        self.process = SystemdFixedPythonProcess(p, hashlib.sha256(p.read_bytes()).hexdigest())
        self.limits = ProcessLimits(cpu_seconds=1, wall_seconds=2, output_bytes=8192)
        self.checker = lambda *_: {'passed': True, 'detail': 'Synthetic measured fixture'}
        identity = packet_executor_identity(program_sha256=self.process.sha256, checker_sha256='b'*64,
            input_ref=f.evidence_ref, limits=self.limits, tasks_max=self.process.tasks_max)
        f.params['executor_sha256'] = identity; f.session = RegistryBranchSession(f.registry, **f.params)
        self.authority = True; self.launches = 0
        self.adapter = FixedPacketExecutor(f.session, self.process, input_ref=f.evidence_ref, limits=self.limits,
            checker=lambda *a:self.checker(*a), checker_sha256='b'*64, authorize=lambda _:self.authority)
        f.handlers = f.make_handlers(self.adapter); f.worker = f.make_worker()

    def task(self, **kw):
        f = self.fixture; return f.task(artifact_refs=[deepcopy(f.frame_ref), deepcopy(f.evidence_ref)], **kw)

    def run(self, result=None):
        # unittest.TestCase.run must retain its standard meaning.
        return super().run(result)

    def process_result(self, raw, **kw):
        self.launches += 1
        if kw['authorize']({'phase':'synthetic_process'}) is not True: raise PermissionError('revoked')
        return dict(schema='merlin-systemd-process-result/1', status='completed',
            input_sha256=hashlib.sha256(raw).hexdigest(), program_sha256=self.process.sha256,
            kernel_setup={'uid':1001,'program_sha256':self.process.sha256}, stdout='ok',
            qualification=False,promotion_authority=False)

    def step(self):
        with patch.object(self.process,'run',side_effect=self.process_result): return self.fixture.worker.run_once()

    def test_actual_handler_records_process_and_replays(self):
        f=self.fixture;f.enqueue(self.task());a=self.step();self.assertEqual(a['status'],'completed')
        f.enqueue(self.task(),key='duplicate');b=self.step();self.assertEqual(a['receipt'],b['receipt']);self.assertEqual(self.launches,1)

    def test_missing_input_ref_blocks(self):
        f=self.fixture;f.enqueue(f.task());self.assertNotEqual(self.step()['status'],'completed');self.assertEqual(self.launches,0)

    def test_truthy_authority_cannot_launch(self):
        self.authority=1;self.fixture.enqueue(self.task());self.assertNotEqual(self.step()['status'],'completed');self.assertEqual(self.launches,0)

    def test_failure_after_ack_boundary_does_not_repeat(self):
        f=self.fixture;f.enqueue(self.task())
        with patch.object(f.outbox,'acknowledge',side_effect=OSError('ack failure')):self.assertEqual(self.step()['status'],'pending')
        self.assertEqual(self.step()['status'],'completed');self.assertEqual(self.launches,1)

    def test_checker_mutation_does_not_rewrite_process_receipt(self):
        def check(raw,result):result['stdout']='forged';return {'passed':True,'detail':'fixture'}
        self.checker=check;f=self.fixture;f.enqueue(self.task());self.assertEqual(self.step()['status'],'completed')
        record=f.session._read('processes/a.json')[0];self.assertEqual(record['process']['stdout'],'ok')

    def test_checker_failure_blocks_dependent_branch(self):
        self.checker=lambda *_:{'passed':False,'detail':'Measured mismatch'}
        f=self.fixture;f.enqueue(self.task());self.assertEqual(self.step()['status'],'completed')
        self.assertEqual(f.session.status()['branches'],[{'id':'a','status':'failed_local_check'},{'id':'b','status':'waiting'}])

    def test_truthy_checker_is_rejected_and_not_repeated(self):
        self.checker=lambda *_:{'passed':1,'detail':'bad'}
        f=self.fixture;f.enqueue(self.task());self.assertNotEqual(self.step()['status'],'completed')
        self.assertNotEqual(self.step()['status'],'completed');self.assertEqual(self.launches,1)

    def test_changed_process_hash_rejected_before_launch(self):
        self.process.sha256='f'*64;self.fixture.enqueue(self.task());self.assertNotEqual(self.step()['status'],'completed')
        self.assertEqual(self.launches,0)

    def test_wrong_source_or_privileged_receipt_rejected(self):
        original=self.process_result
        for field,value in [('input_sha256','f'*64),('qualification',True),('kernel_setup',{'uid':0,'program_sha256':self.process.sha256})]:
            def wrong(raw,field=field,value=value,**kw):r=original(raw,**kw);r[field]=value;return r
            with self.subTest(field=field),patch.object(self.process,'run',side_effect=wrong):
                # Separate sessions avoid testing the intentional unresolved-intent fence instead of validation.
                f=self.fixture;f.params['session_id']='case-'+field;f.session=RegistryBranchSession(f.registry,**f.params)
                a=FixedPacketExecutor(f.session,self.process,input_ref=f.evidence_ref,limits=self.limits,
                    checker=self.checker,checker_sha256='b'*64,authorize=lambda _:True)
                f.handlers=f.make_handlers(a);f.worker=f.make_worker();f.enqueue(self.task(task_id=field),key=field)
                self.assertNotEqual(f.worker.run_once()['status'],'completed')

    def test_receipt_size_budget_cannot_grow(self):
        with self.assertRaises(ValueError):packet_executor_identity(program_sha256=self.process.sha256,
            checker_sha256='b'*64,input_ref=self.fixture.evidence_ref,limits=ProcessLimits())


if __name__=='__main__':unittest.main()
