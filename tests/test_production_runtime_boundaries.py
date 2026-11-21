"""Defect controls for connection lifetime, stale leases and bounded path queries."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
import test_branch_worker as fixtures
from merlin.hypothesis_ledger import HypothesisLedger
from merlin.project_registry import MerlinRegistry


class LedgerConnectionLifetimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.connections=[]; self.closed=set(); original=sqlite3.connect; owner=self
        class Tracked(sqlite3.Connection):
            def close(self): owner.closed.add(id(self)); return super().close()
        def connect(*args,**kw):
            conn=original(*args,**{**kw,'factory':Tracked}); self.connections.append(conn); return conn
        self.patch=patch('merlin.hypothesis_ledger.sqlite3.connect',side_effect=connect)
        self.patch.start(); self.addCleanup(self.patch.stop)
        self.addCleanup(lambda:[c.close() for c in self.connections])
        self.ledger=HypothesisLedger(Path(self.tmp.name)/'ledger.sqlite3')

    def test_success_paths_close_connections_without_gc(self):
        l=self.ledger; l.create('h','Synthetic claim'); l.add_evidence('h','experiment','one',idempotency_key='x')
        l.add_evidence('h','experiment','one',idempotency_key='x'); l.get('h'); l.evidence('h')
        l.set_status('h','computationally_tested'); l.list_hypotheses()
        self.assertEqual({id(c) for c in self.connections},self.closed)

    def test_exception_paths_close_and_rollback_without_gc(self):
        l=self.ledger; l.create('h','Synthetic claim')
        with self.assertRaises(KeyError): l.get('missing')
        with self.assertRaises(KeyError): l.add_evidence('missing','source','x')
        l.add_evidence('h','source','one',idempotency_key='x')
        with self.assertRaises(ValueError): l.add_evidence('h','source','two',idempotency_key='x')
        self.assertEqual(len(l.evidence('h')),1); self.assertEqual({id(c) for c in self.connections},self.closed)


class WorkerBoundaryTests(unittest.TestCase):
    setUp=fixtures.BranchWorkerTests.setUp
    evaluate=fixtures.BranchWorkerTests.evaluate
    make_handlers=fixtures.BranchWorkerTests.make_handlers
    make_worker=fixtures.BranchWorkerTests.make_worker
    task=fixtures.BranchWorkerTests.task
    enqueue=fixtures.BranchWorkerTests.enqueue

    def test_expired_lease_cannot_continue_before_heartbeat_notices(self):
        event=self.enqueue(); effects=[]
        def handler(task,context):
            with closing(self.outbox._connect()) as db,db:
                db.execute('UPDATE event_outbox SET lease_expires_at=? WHERE event_id=?',(time.time()-10,event['event_id']))
            context.check_cancelled(); effects.append('must-not-run'); return {}
        result=self.make_worker(handlers={'research':handler}).run_once()
        self.assertEqual(result['status'],'lease_lost'); self.assertEqual(effects,[])

    def test_monotonic_deadline_survives_wall_clock_rollback(self):
        self.enqueue(); effects=[]
        def handler(task,context):
            with patch('merlin.hermes_worker.time.monotonic',return_value=time.monotonic()+100), \
                 patch('merlin.hermes_worker.time.time',return_value=time.time()-1000):
                context.check_cancelled(); effects.append('must-not-run')
            return {}
        self.make_worker(handlers={'research':handler}).run_once(now=time.time())
        self.assertEqual(effects,[])

    def test_legacy_interrupted_task_fences_successor(self):
        self.enqueue(); original=self.session._put_path
        def crash(path,body):
            if path.endswith('/result.json'): raise OSError('before publication')
            return original(path,body)
        with patch.object(self.session,'_put_path',side_effect=crash): self.worker.run_once()
        self.enqueue(self.task('tick-2'),key='second')
        for _ in range(5): self.worker.run_once()
        self.assertEqual(self.calls,['a'])


class RegistryBoundedQueryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.registry=MerlinRegistry(Path(self.tmp.name)/'registry'); self.registry.register_project('p','fixture')
        for p in ('task/a/request.json','task/b/request.json','task/b/result.json','task/%literal/request.json','other/request.json'):
            self.registry.put_artifact('p',p,b'{}','application/json')

    def test_truncation_is_explicit(self):
        r=self.registry.artifact_paths('p',prefix='task/',suffix='/request.json',limit=2)
        self.assertIs(r['truncated'],True); self.assertEqual(len(r['paths']),2)
        r=self.registry.artifact_paths('p',prefix='task/',suffix='/request.json',limit=3)
        self.assertIs(r['truncated'],False); self.assertEqual(len(r['paths']),3)

    def test_prefix_is_literal_not_sql_wildcard(self):
        self.assertEqual(self.registry.artifact_paths('p',prefix='task/%literal/')['paths'],['task/%literal/request.json'])

    def test_bad_limits_and_unknown_project_fail(self):
        for limit in (True,0,4097,1.5):
            with self.subTest(limit=limit),self.assertRaises(ValueError): self.registry.artifact_paths('p',limit=limit)
        with self.assertRaises(KeyError): self.registry.artifact_paths('missing')

if __name__=='__main__': unittest.main()
