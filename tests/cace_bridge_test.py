#!/usr/bin/env python3
"""Transport integration tests using disposable local git repositories."""
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cace_bridge', ROOT / 'python/cace_bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
NOW = datetime(2026, 9, 26, 16, 0, tzinfo=timezone.utc)
SOURCE = 'a' * 40


def quota():
    return {'schema_version': 1, 'accounts': [{
        'owner': 'morganaspim', 'checked_at': NOW.isoformat(),
        'billing_cycle': '2026-09', 'paid_overage_blocked': True,
        'free_linux_minutes_remaining': 3, 'evidence': 'local test fixture only',
    }]}


class QuotaTests(unittest.TestCase):
    def test_minimum_reservation_is_accepted(self):
        bridge.check_quota(quota(), 'morganaspim', 3, NOW)

    def test_invalid_budget_evidence_fails_closed(self):
        mutations = [
            {'paid_overage_blocked': False}, {'paid_overage_blocked': 'true'},
            {'free_linux_minutes_remaining': 2}, {'free_linux_minutes_remaining': True},
            {'checked_at': (NOW - timedelta(hours=6, seconds=1)).isoformat()},
            {'checked_at': (NOW + timedelta(seconds=1)).isoformat()},
            {'checked_at': '2026-09-26T16:00:00'}, {'checked_at': None},
            {'billing_cycle': '2026-08'}, {'evidence': ''},
        ]
        for update in mutations:
            with self.subTest(update=update):
                document = quota()
                document['accounts'][0].update(update)
                with self.assertRaises(ValueError):
                    bridge.check_quota(document, 'morganaspim', 3, NOW)

    def test_accounts_cannot_share_a_reservation(self):
        with self.assertRaises(bridge.BridgeError):
            bridge.check_quota(quota(), 'Mannyspiro', 3, NOW)
        document = quota()
        document['accounts'] *= 2
        with self.assertRaises(bridge.BridgeError):
            bridge.check_quota(document, 'morganaspim', 3, NOW)

    def test_example_never_authorizes_paid_work(self):
        document = bridge.read_json(ROOT / 'config/cace_free_quota.example.json')
        with self.assertRaises(ValueError):
            bridge.check_quota(document, 'morganaspim', 3, NOW)

    def test_duplicate_keys_and_oversized_records_are_rejected(self):
        for raw in ['{"status":"pending","status":"pass"}', '[]', '{"x":"' + 'a' * 9000 + '"}']:
            with self.subTest(raw=raw[:60]), self.assertRaises(bridge.BridgeError):
                bridge.decode_json(raw)


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cace-bridge-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / 'remote.git'
        subprocess.run(['git', 'init', '--quiet', '--bare', '--initial-branch=main', str(self.remote)], check=True)
        self.work = self.root / 'work'
        self.work.mkdir()
        self.git = bridge.GitRemote(self.work, str(self.remote))
        blob = self.git.git('hash-object', '-w', '--stdin', input='Main sentinel; never execute\n').stdout.strip()
        self.git.git('update-index', '--add', '--cacheinfo', '100644,' + blob + ',README.md')
        tree = self.git.git('write-tree').stdout.strip()
        self.base = self.git.git('-c', 'user.name=test', '-c', 'user.email=test@example.invalid',
                                 'commit-tree', tree, input='Initial test commit\n').stdout.strip()
        self.git.git('push', '--quiet', 'origin', self.base + ':refs/heads/main')
        # Transport starts with an empty index, as in its fresh temporary repo.
        self.git.git('read-tree', '--empty')
        self.receipt_path = self.root / 'receipt.json'
        self.workflow = (ROOT / 'ops/cace/capability-probe.yml').read_text()

    def dispatch(self):
        return bridge.dispatch(self.git, SOURCE, quota(), self.receipt_path, self.workflow, NOW)

    def publish(self, receipt, result, path='bridge/result.json', mode='100644'):
        head = self.git.fetch_branch(receipt['branch'])
        self.git.git('read-tree', head)
        content = result if isinstance(result, str) else bridge.encode_json(result)
        blob = self.git.git('hash-object', '-w', '--stdin', input=content).stdout.strip()
        self.git.git('update-index', '--add', '--cacheinfo', mode + ',' + blob + ',' + path)
        tree = self.git.git('write-tree').stdout.strip()
        commit = self.git.git('-c', 'user.name=test', '-c', 'user.email=test@example.invalid',
                               'commit-tree', tree, '-p', head, input='Test result\n').stdout.strip()
        self.git.git('push', '--quiet', 'origin', commit + ':refs/heads/' + receipt['branch'])

    @staticmethod
    def observation(receipt):
        return {'schema_version': 1, 'kind': 'capability-probe', 'request': receipt['request'],
                'dispatch_commit': receipt['dispatch_commit'], 'run_id': 123,
                'status': 'observed', 'formal_verified': False, 'promotion_authority': False,
                'capabilities': {'architecture': 'aarch64', 'free_disk_bytes': 123456,
                                 'tools': {'python3': True}}}

    def test_complete_roundtrip_preserves_main_and_returns_bound_evidence(self):
        receipt = self.dispatch()
        self.assertEqual(self.git.head(), self.base)
        head = self.git.fetch_branch(receipt['branch'])
        self.assertEqual(head, receipt['dispatch_commit'])
        paths = self.git.git('ls-tree', '-r', '--name-only', head).stdout.splitlines()
        self.assertEqual(paths, ['.github/workflows/expert-robot-capability.yml', 'bridge/request.json'])
        self.assertEqual(bridge.collect(self.git, receipt)['status'], 'pending')
        self.publish(receipt, self.observation(receipt))
        self.assertEqual(bridge.collect(self.git, receipt), self.observation(receipt))
        self.assertEqual(self.git.head(), self.base)

    def test_retry_reuses_request_without_another_push(self):
        receipt = self.dispatch()
        before = self.git.fetch_branch(receipt['branch'])
        again = bridge.dispatch(self.git, SOURCE, {}, self.receipt_path, self.workflow, NOW)
        self.assertEqual(again, receipt)
        self.assertEqual(self.git.fetch_branch(receipt['branch']), before)

    def test_invalid_quota_stops_before_dispatch_or_receipt(self):
        with self.assertRaises(bridge.BridgeError):
            bridge.dispatch(self.git, SOURCE, {}, self.receipt_path, self.workflow, NOW)
        self.assertFalse(self.receipt_path.exists())
        self.assertEqual(len(self.git.git('ls-remote', '--heads', 'origin').stdout.splitlines()), 1)

    def test_existing_branch_cannot_be_replaced(self):
        receipt = self.dispatch()
        with self.assertRaises(bridge.BridgeError):
            self.git.push_new(self.base, receipt['branch'])
        self.assertEqual(self.git.fetch_branch(receipt['branch']), receipt['dispatch_commit'])

    def test_replayed_receipt_for_other_source_is_rejected(self):
        self.dispatch()
        with self.assertRaises(bridge.BridgeError):
            bridge.dispatch(self.git, 'b' * 40, quota(), self.receipt_path, self.workflow, NOW)

    def test_branch_path_injection_is_rejected(self):
        receipt = self.dispatch()
        receipt['branch'] = '--upload-pack=unsafe'
        with self.assertRaises(bridge.BridgeError):
            bridge.collect(self.git, receipt)

    def test_mutated_remote_request_is_rejected(self):
        receipt = self.dispatch()
        changed = dict(receipt['request'], expert_robot_commit='b' * 40)
        self.publish(receipt, changed, path='bridge/request.json')
        with self.assertRaises(bridge.BridgeError):
            bridge.collect(self.git, receipt)

    def test_capabilities_cannot_claim_proof_or_promotion(self):
        receipt = self.dispatch()
        mutations = [{'formal_verified': True}, {'formal_verified': 'false'},
                     {'promotion_authority': True}, {'status': 'pass'},
                     {'dispatch_commit': 'b' * 40}, {'run_id': True},
                     {'request': dict(receipt['request'], expert_robot_commit='b' * 40)}]
        for update in mutations:
            with self.subTest(update=update):
                result = self.observation(receipt)
                result.update(update)
                with self.assertRaises(bridge.BridgeError):
                    bridge.validate_result(result, receipt)

    def test_remote_symlink_result_is_rejected(self):
        receipt = self.dispatch()
        self.publish(receipt, '/etc/passwd', mode='120000')
        with self.assertRaises(bridge.BridgeError):
            bridge.collect(self.git, receipt)

    def test_remote_oversized_result_is_rejected(self):
        receipt = self.dispatch()
        self.publish(receipt, 'a' * 9000)
        with self.assertRaises(bridge.BridgeError):
            bridge.collect(self.git, receipt)

    def test_transport_failure_is_not_reported_as_pending(self):
        receipt = self.dispatch()
        self.git.git('remote', 'set-url', 'origin', str(self.root / 'missing.git'))
        with self.assertRaises(bridge.BridgeError):
            bridge.collect(self.git, receipt)

    def test_missing_remote_branch_is_not_reported_as_pending(self):
        receipt = self.dispatch()
        self.git.git('push', '--quiet', 'origin', ':refs/heads/' + receipt['branch'])
        with self.assertRaises(bridge.BridgeError):
            bridge.collect(self.git, receipt)


if __name__ == '__main__':
    unittest.main(verbosity=2)
