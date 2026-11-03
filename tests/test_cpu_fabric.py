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
