"""Bounded, read-only host observations; no allocator, subprocess, or GPU probe.

Unknown is represented as None. Linux /proc totals can describe the host rather
than the container, so cgroup limits and process RSS are separate observations.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import re
import shutil

MAX_READ = 64 * 1024
MAX_BYTES = 2**63 - 1


def _read(path, limit=MAX_READ):
    try:
        with Path(path).open("rb") as source:
            raw = source.read(limit + 1)
        return raw.decode("ascii") if len(raw) <= limit else None
    except (OSError, UnicodeError):
        return None


def _kb_fields(path, names):
    text = _read(path)
    result = {name: None for name in names}
    if text is None:
        return result
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if not sep or key not in result:
            continue
        match = re.fullmatch(r"\s*([0-9]{1,16})\s+kB\s*", value)
        if match and int(match[1]) <= MAX_BYTES // 1024:
            result[key] = int(match[1]) * 1024
    return result


def _cgroup_bytes(path):
    value = _read(path, 64)
    if value is None or not value.strip().isascii() or not value.strip().isdecimal():
        return None
    number = int(value.strip())
    return number if 0 <= number <= MAX_BYTES else None


def _cgroup_snapshot(proc_root, group_root):
    # v2 only: do not manufacture a container limit when mount visibility is
    # incomplete. Ancestor limits can be stricter than this visible scope.
    relative = None
    text = _read(proc_root / "self/cgroup", 4096)
    if text:
        for line in text.splitlines():
            if line.startswith("0::"):
                value = line[3:]
                if value.startswith("/") and ".." not in Path(value).parts:
                    relative = value.lstrip("/")
                break
    candidates = ([group_root / relative] if relative is not None else []) + [group_root]
    for folder in candidates:
        current = _cgroup_bytes(folder / "memory.current")
        limit_text = _read(folder / "memory.max", 64)
        if current is not None and limit_text is not None:
            return {"version": 2, "current_bytes": current,
                    "limit_bytes": _cgroup_bytes(folder / "memory.max"),
                    "unlimited_at_visible_scope": limit_text.strip() == "max",
                    "scope": "Visible memory cgroup; may include other processes and file cache; ancestor limits may apply."}
    return {"version": None, "current_bytes": None, "limit_bytes": None,
            "unlimited_at_visible_scope": None, "scope": "No readable v2 memory cgroup observation."}


def resource_snapshot(root, data_dir, *, model_pid=None, proc_root=Path("/proc"),
                      group_root=Path("/sys/fs/cgroup"), dev_root=Path("/dev")):
    """Inspect only this server, its owned model PID, and bounded kernel files."""
    root, data_dir = Path(root), Path(data_dir)
    proc_root, group_root, dev_root = Path(proc_root), Path(group_root), Path(dev_root)
    memory = _kb_fields(proc_root / "meminfo", ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"))
    own = _kb_fields(proc_root / "self/status", ("VmRSS", "VmHWM"))
    child = (_kb_fields(proc_root / str(model_pid) / "status", ("VmRSS", "VmHWM"))
             if type(model_pid) is int and 0 < model_pid <= 2**31 - 1 else {"VmRSS": None, "VmHWM": None})
    try:
        space = shutil.disk_usage(data_dir)
        storage = {"total_bytes": space.total, "available_bytes": space.free,
                   "scope": "Filesystem containing Studio state; physical drive type and speed are unmeasured."}
    except OSError:
        storage = {"total_bytes": None, "available_bytes": None, "scope": "Filesystem observation unavailable."}
    # Node presence is not proof that a driver can execute a model. Do not
    # call nvidia-smi, enumerate users' processes, or import a CUDA runtime.
    nodes = []
    for i in range(32):
        for path in (dev_root / ("nvidia" + str(i)), dev_root / "dri" / ("renderD" + str(128 + i))):
            if path.exists():
                nodes.append(str(path.relative_to(dev_root)))
    try:
        from linux_preflight import check_linux_host
        compatibility = check_linux_host(root, data_dir=data_dir, probe_binary=False)
    except ModuleNotFoundError as exc:
        if exc.name != "linux_preflight":
            raise
        compatibility = {"status": "not_available", "checks": []}
    return {
        "schema": "merlin-studio-resources/1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "host": {"system": platform.system(), "architecture": platform.machine(), "logical_cpus": os.cpu_count()},
        "memory": {"total_bytes": memory["MemTotal"], "available_bytes": memory["MemAvailable"],
                   "swap_total_bytes": memory["SwapTotal"], "swap_free_bytes": memory["SwapFree"],
                   "scope": "Kernel MemTotal/MemAvailable; these may describe the host, not a container allowance."},
        "processes": {"studio_rss_bytes": own["VmRSS"], "studio_peak_rss_bytes": own["VmHWM"],
                      "owned_model_rss_bytes": child["VmRSS"], "owned_model_peak_rss_bytes": child["VmHWM"],
                      "scope": "Separate process RSS; shared pages may be counted in both. External model processes are not inspected."},
        "cgroup": _cgroup_snapshot(proc_root, group_root),
        "storage": storage,
        "gpu": {"observed_device_nodes": nodes, "compute_readiness": "not_probed", "vram_bytes": None,
                "scope": "Device-node observations only; no GPU allocation, utilization, or driver qualification."},
        "linux_compatibility": compatibility,
        "virtual_resources": {
            "studio_allocator": "managed_by_model_provider",
            "parallax_profile": "separate_offline_cli",
            "scope": "Parallax's optional tensor pager and CPU logical accelerator use explicit owned-buffer budgets. They do not add physical RAM or GPU cores, and do not cap Studio's Qwen process."
        }
    }
