"""Merlin CPU Compute Fabric: bounded, reproducible CPU-native kernels."""
from .benchmarks import run_suite
from .scheduler import run_scheduler_benchmark

__all__ = ["run_suite", "run_scheduler_benchmark"]
