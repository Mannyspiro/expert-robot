import threading
import time
import unittest

from python.merlin.hermes_service import HermesWorkerService


class IdleWorker:
    def __init__(self):
        self.calls = 0
        self.called = threading.Event()

    def run_once(self):
        self.calls += 1
        self.called.set()
        return None


class FlakyWorker:
    def __init__(self):
        self.calls = 0
        self.recovered = threading.Event()

    def run_once(self):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("transient storage fault")
        self.recovered.set()
        return {"status": "completed"}


class BlockingWorker:
    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()

    def run_once(self):
        self.entered.set()
        self.release.wait(timeout=2)
        return None


class HermesWorkerServiceTests(unittest.TestCase):
    def test_start_is_idempotent_and_stop_is_graceful(self):
        worker = IdleWorker()
        service = HermesWorkerService(worker, idle_seconds=0.01)
        self.assertTrue(service.start())
        self.assertFalse(service.start())
        self.assertTrue(worker.called.wait(timeout=1))
        self.assertTrue(service.health()["ready"])
        self.assertTrue(service.stop(timeout_seconds=1))
        self.assertEqual(service.health()["status"], "stopped")
        self.assertFalse(service.health()["thread_alive"])

    def test_transient_worker_errors_back_off_and_recover(self):
        worker = FlakyWorker()
        service = HermesWorkerService(
            worker, idle_seconds=0.01, max_backoff_seconds=0.02
        )
        service.start()
        self.assertTrue(worker.recovered.wait(timeout=1))
        health = service.health()
        self.assertEqual(health["errors"], 1)
        self.assertGreaterEqual(health["processed"], 1)
        self.assertEqual(health["authority"], "bounded_execution_only")
        self.assertFalse(health["promotion_authority"])
        self.assertTrue(service.stop(timeout_seconds=1))

    def test_stop_reports_a_handler_that_does_not_exit(self):
        worker = BlockingWorker()
        service = HermesWorkerService(worker, idle_seconds=0.01)
        service.start()
        self.assertTrue(worker.entered.wait(timeout=1))
        self.assertFalse(service.stop(timeout_seconds=0.01))
        self.assertEqual(service.health()["status"], "stopping")
        worker.release.set()
        self.assertTrue(service.stop(timeout_seconds=1))
        self.assertEqual(service.health()["status"], "stopped")


if __name__ == "__main__":
    unittest.main()
