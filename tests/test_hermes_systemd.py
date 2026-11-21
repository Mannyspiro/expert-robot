"""Admission/command controls. Actual kernel tests are the separate OCI drill."""
from dataclasses import replace
import hashlib
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from merlin.hermes_process import ProcessLimits, ProcessIsolationUnavailable, read_fixed_program
from merlin.hermes_systemd import SystemdFixedPythonProcess, _properties


class SystemdAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'fixed.py'; self.path.write_text('print(42)')
        self.sha=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.runner=SystemdFixedPythonProcess(self.path,self.sha)
        self.context=SimpleNamespace(resource_budget={'cpu_cores':1,'memory_bytes':128*1024*1024,
            'max_wall_seconds':10,'compute_budget_units':1},deadline_epoch=time.time()+15,check_cancelled=lambda:None)
        self.limits=ProcessLimits(cpu_seconds=1,wall_seconds=3)

    def run_tool(self,**kw):
        with patch.object(self.runner,'available',return_value=True):
            return self.runner.run(b'{}',context=self.context,limits=kw.pop('limits',self.limits),authorize=kw.pop('authorize',lambda _:True),**kw)

    def test_missing_manager_fails_before_spawn(self):
        with patch.object(self.runner,'available',return_value=False),patch('subprocess.Popen',side_effect=AssertionError('spawned')):
            with self.assertRaises(ProcessIsolationUnavailable): self.runner.run(b'{}',limits=self.limits,context=self.context,authorize=lambda _:True)

    def test_no_privilege_escalation_is_attempted(self):
        with patch('merlin.hermes_systemd.os.geteuid',return_value=1000):
            self.assertIs(SystemdFixedPythonProcess.available(),False)

    def test_truthy_authorization_rejected_before_spawn(self):
        with patch('subprocess.Popen',side_effect=AssertionError('spawned')):
            with self.assertRaises(PermissionError): self.run_tool(authorize=lambda _:1)

    def test_resource_expansion_rejected(self):
        with self.assertRaises(PermissionError): self.run_tool(limits=replace(self.limits,memory_bytes=256*1024*1024))

    def test_expired_deadline_rejected(self):
        self.context.deadline_epoch=time.time()-1
        with self.assertRaises(TimeoutError): self.run_tool()

    def test_remaining_task_time_respected(self):
        self.context.deadline_epoch=time.time()+.2
        with self.assertRaises(PermissionError): self.run_tool()

    def test_changed_program_hash_rejected(self):
        self.path.write_text('print(99)')
        with self.assertRaisesRegex(ValueError,'identity'): self.run_tool()

    def test_symlink_rejected(self):
        link=self.path.with_name('link.py'); link.symlink_to(self.path)
        with self.assertRaises(OSError): read_fixed_program(link,self.sha)

    def test_controller_properties_preserve_hard_limits(self):
        p=_properties(self.limits,8)
        self.assertEqual(p['MemoryMax'],str(64*1024*1024)); self.assertEqual(p['CPUQuota'],'100%')
        self.assertEqual(p['TasksMax'],'8'); self.assertEqual(p['KillMode'],'control-group')
        self.assertEqual(p['DynamicUser'],'yes'); self.assertEqual(p['NoNewPrivileges'],'yes')
        self.assertEqual(p['MemorySwapMax'],'0'); self.assertEqual(p['CapabilityBoundingSet'],'')
        self.assertEqual(p['RuntimeMaxSec'],'3s'); self.assertIn('size=16M',p['TemporaryFileSystem'])

    def test_task_ceiling_has_strict_boundaries(self):
        for value in (True,0,33,1.5):
            with self.subTest(value=value),self.assertRaises(ValueError): _properties(self.limits,value)

    def test_invalid_wall_limits_rejected(self):
        for value in (True,float('inf'),float('nan'),0,121):
            with self.subTest(value=value),self.assertRaises(ValueError): _properties(replace(self.limits,wall_seconds=value),8)

    def test_noninteger_task_budget_rejected(self):
        self.context.resource_budget['compute_budget_units']=float('inf')
        with self.assertRaises(ValueError): self.run_tool()

if __name__=='__main__': unittest.main()

class ManagerStreamTests(unittest.TestCase):
    def test_manager_opens_streams_without_passing_file_descriptors(self):
        from merlin.hermes_systemd import _command
        properties=_properties(ProcessLimits(),8)
        properties.update(StandardInput='file:/run/fixed/stdin',StandardOutput='file:/run/fixed/stdout',StandardError='file:/run/fixed/stderr')
        args=_command('merlin-fixed-fixture.service',properties,{'unit':'merlin-fixed-fixture.service'})
        self.assertNotIn('--pipe',args)
        for stream in ('Input','Output','Error'):
            self.assertTrue(any(x.startswith('--property=Standard'+stream+'=file:/run/') for x in args))
        self.assertIn('--property=NoNewPrivileges=yes',args)
        self.assertIn('--property=KillMode=control-group',args)
        self.assertIn('--property=PrivateNetwork=yes',args)
