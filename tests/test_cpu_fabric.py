import unittest
from merlin.cpu_fabric.kernels import tiled_matmul
from merlin.cpu_fabric.scheduler import run_scheduler_benchmark
from merlin.cpu_fabric.benchmarks import run_suite

class CpuFabricTests(unittest.TestCase):
    def test_tiled_matmul(self):
        self.assertEqual(tiled_matmul([[1,2],[3,4]], [[5,6],[7,8]], 1), [[19,22],[43,50]])
    def test_scheduler_determinism(self):
        self.assertTrue(run_scheduler_benchmark(64,2)["verified_equal"])
    def test_benchmark_accuracy(self):
        self.assertTrue(run_suite(12,4)["verified"])

if __name__ == "__main__": unittest.main()

from merlin.cpu_fabric.ideonomy import enumerate_candidates, rank_measured

class IdeonomyTests(unittest.TestCase):
    def test_candidates_are_bounded_and_repeatable(self):
        self.assertEqual(enumerate_candidates(12), enumerate_candidates(12))
        self.assertEqual(len(enumerate_candidates(12)), 12)
    def test_unverified_candidates_are_not_ranked(self):
        self.assertEqual(rank_measured([{"verified": False}]), [])
    def test_quality_gate_is_enforced(self):
        bad={"verified":True,"peak_rss_bytes":1024,"tokens_per_second":10,
             "task_quality":0.7,"baseline_task_quality":0.9}
        self.assertEqual(rank_measured([bad]), [])
