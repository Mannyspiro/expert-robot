"""Measure Avrea runner resources and emit a typed MCFC capacity snapshot."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any


def read_text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None


def command_output(args: list[str], timeout: int = 5) -> str | None:
    try:
        result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def parse_cpu_capacity(cpu_max: str | None, host_cpu_count: int | None,
                       *, v1_quota: str | None = None,
                       v1_period: str | None = None) -> tuple[int, float | None]:
    host = max(0, int(host_cpu_count or 0))
    if cpu_max:
        parts = cpu_max.split()
        if len(parts) == 2:
            if parts[0] == "max":
                return host, None
            try:
                quota, period = int(parts[0]), int(parts[1])
            except ValueError:
                quota, period = 0, 0
            if quota > 0 and period > 0:
                fractional = quota / period
                return min(host, math.floor(fractional)), fractional
    if v1_quota and v1_period:
        try:
            quota, period = int(v1_quota), int(v1_period)
        except ValueError:
            quota, period = 0, 0
        if quota < 0:
            return host, None
        if quota > 0 and period > 0:
            fractional = quota / period
            return min(host, math.floor(fractional)), fractional
        if quota == 0 and period > 0:
            return 0, 0.0
    return host, None


def _mem_total_bytes(meminfo_text: str | None) -> int | None:
    if not meminfo_text:
        return None
    for line in meminfo_text.splitlines():
        if line.startswith("MemTotal:"):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    return int(parts[1]) * 1024
                except ValueError:
                    return None
    return None


def effective_memory_bytes(memory_max: str | None, meminfo_text: str | None) -> int:
    host_total = _mem_total_bytes(meminfo_text)
    cgroup_limit = None
    if memory_max and memory_max != "max":
        try:
            cgroup_limit = int(memory_max)
        except ValueError:
            pass
    known = [v for v in (host_total, cgroup_limit) if v is not None and v > 0]
    return min(known) if known else 0


def parse_gpu_capacity(output: str | None) -> tuple[int | None, int | None, list[str]]:
    if output is None:
        return None, None, []
    if not output.strip():
        return 0, 0, []
    names, total_bytes = [], 0
    for line in output.splitlines():
        if not line.strip():
            continue
        name, separator, memory = line.rpartition(",")
        if not separator:
            return None, None, []
        try:
            memory_mib = int(memory.strip())
        except ValueError:
            return None, None, []
        if memory_mib < 0:
            return None, None, []
        names.append(name.strip())
        total_bytes += memory_mib * 1024 * 1024
    return len(names), total_bytes, names


def _sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_mcfc_capacity_snapshot(*, cpu_cores: int, memory_bytes: int,
                                 gpu_count: int | None, gpu_memory_bytes: int | None,
                                 observed_at: str, raw_measurements: dict[str, Any]) -> dict[str, Any]:
    body = {
        "schema": "mcfc-capacity-snapshot/0.1",
        "cpu_cores": cpu_cores,
        "memory_bytes": memory_bytes,
        "gpu_count": gpu_count,
        "gpu_memory_bytes": gpu_memory_bytes,
        "compute_budget_units": None,
        "observed_at": observed_at,
        "source": "avrea-runner-resource-probe",
        "raw_measurements_sha256": _sha256(raw_measurements),
    }
    return {**body, "evidence_sha256": _sha256(body)}


def probe() -> dict[str, Any]:
    meminfo = read_text("/proc/meminfo")
    cpu_max = read_text("/sys/fs/cgroup/cpu.max")
    v1_quota = read_text("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
    v1_period = read_text("/sys/fs/cgroup/cpu/cpu.cfs_period_us")
    memory_max = read_text("/sys/fs/cgroup/memory.max")
    memory_current = read_text("/sys/fs/cgroup/memory.current")
    cpu_cores, fractional_cpu = parse_cpu_capacity(cpu_max, os.cpu_count(),
                                                    v1_quota=v1_quota, v1_period=v1_period)
    memory_bytes = effective_memory_bytes(memory_max, meminfo)
    gpu_output = command_output(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
    gpu_count, gpu_memory_bytes, gpu_names = parse_gpu_capacity(gpu_output)
    disk = {}
    for name, path in (("workspace", "."), ("tmp", "/tmp")):
        try:
            usage = shutil.disk_usage(path)
            disk[name] = {"total_bytes": usage.total, "used_bytes": usage.used, "free_bytes": usage.free}
        except OSError:
            disk[name] = None
    observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    raw = {
        "platform": platform.platform(), "machine": platform.machine(),
        "host_cpu_count": os.cpu_count(), "cpu_max": cpu_max,
        "cpu_v1_quota": v1_quota, "cpu_v1_period": v1_period,
        "fractional_cpu_quota": fractional_cpu, "memory_max": memory_max,
        "memory_current": memory_current, "meminfo": meminfo,
        "gpu_probe_available": gpu_output is not None, "gpu_names": gpu_names, "disk": disk,
    }
    mcfc = build_mcfc_capacity_snapshot(
        cpu_cores=cpu_cores, memory_bytes=memory_bytes,
        gpu_count=gpu_count, gpu_memory_bytes=gpu_memory_bytes,
        observed_at=observed_at, raw_measurements=raw,
    )
    return {
        "schema": "merlin-avrea-runner-inventory/0.2",
        "observed_at": observed_at, "platform": platform.platform(),
        "machine": platform.machine(), "python": sys.version,
        "raw_measurements": raw, "mcfc_capacity": mcfc,
        "model_download_performed": False,
        "secrets_or_environment_values_recorded": False,
        "compute_budget_note": "Unknown until explicitly configured; no budget inferred from CPU or memory.",
        "gpu_note": "GPU capacity is null when the NVIDIA probe is unavailable; this does not prove no GPU exists.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/runner-inventory/capacity.json")
    args = parser.parse_args()
    result = probe()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
