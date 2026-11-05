"""Bounded ngspice batch adapter for canonical Merlin electrical netlists.

Requires a locally installed ngspice executable. The accepted input is a
restricted passive/independent-source netlist; control, shell, include and
external-file directives are rejected before invoking the engine.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

_COMPONENT = re.compile(r"^[RCLVIDQMNJ][A-Za-z0-9_.:+-]*\s+\S+\s+\S+\s+.+$", re.I)
_ALLOWED_DIRECTIVES = {".title", ".model", ".op", ".tran", ".ac", ".dc", ".print", ".save", ".meas", ".end"}
_FORBIDDEN = re.compile(r"(^\s*\.(?:control|include|lib|shell|exec|external|hdl)\b)|(^\s*(?:shell|source|exec)\b)", re.I)


def validate_netlist(netlist: str) -> str:
    if not isinstance(netlist, str) or not netlist.strip() or len(netlist.encode("utf-8")) > 1_000_000:
        raise ValueError("netlist must be non-empty UTF-8 text no larger than 1 MB")
    lines = netlist.splitlines()
    has_component = False
    has_analysis = False
    has_end = False
    for index, raw in enumerate(lines):
        line = raw.strip()
        if not line or line.startswith("*") or line.startswith("$"):
            continue
        if _FORBIDDEN.search(line):
            raise ValueError("netlist contains a forbidden control or external-file directive")
        if line.startswith("."):
            directive = line.split(None, 1)[0].lower()
            if directive not in _ALLOWED_DIRECTIVES:
                raise ValueError("unsupported ngspice directive on line " + str(index + 1))
            if directive in {".op", ".tran", ".ac", ".dc"}:
                has_analysis = True
            if directive == ".end":
                has_end = True
            continue
        if _COMPONENT.match(line):
            has_component = True
            continue
        # First non-comment, non-directive line is the SPICE title.
        if index == 0:
            continue
        raise ValueError("unsupported netlist statement on line " + str(index + 1))
    if not has_component or not has_analysis or not has_end:
        raise ValueError("netlist requires at least one component, an analysis directive and .end")
    return netlist.rstrip() + "\n"


def run_ngspice(
    netlist: str,
    *,
    timeout_seconds: int = 60,
    max_memory_bytes: int = 1_073_741_824,
) -> dict[str, Any]:
    """Run ngspice in batch mode and return a registry-ready JSON artifact."""
    validated = validate_netlist(netlist)
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 600:
        raise ValueError("timeout_seconds must be between 1 and 600")
    if isinstance(max_memory_bytes, bool) or not isinstance(max_memory_bytes, int) or not 64*1024*1024 <= max_memory_bytes <= 8*1024*1024*1024:
        raise ValueError("max_memory_bytes must be between 64 MiB and 8 GiB")
    executable = shutil.which("ngspice")
    if not executable:
        raise RuntimeError("ngspice executable is not installed or not on PATH")
    with tempfile.TemporaryDirectory(prefix="merlin-ngspice-") as temp:
        root = Path(temp)
        net_path, log_path = root / "input.cir", root / "ngspice.log"
        net_path.write_text(validated, encoding="utf-8")
        command = [executable, "-b", "-o", str(log_path), str(net_path)]
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command, cwd=str(root), capture_output=True, text=True,
                timeout=timeout_seconds, check=False,
                env={"PATH": str(Path(executable).parent), "HOME": str(root), "LANG": "C"},
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("ngspice exceeded the configured wall-time limit") from exc
        elapsed = time.monotonic() - started
        log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        combined = (completed.stdout or "") + "\n" + (completed.stderr or "") + "\n" + log
        if completed.returncode != 0 or re.search(r"\b(error|fatal)\b", combined, re.I):
            raise RuntimeError("ngspice failed: " + combined[-4000:])
        artifact = {
            "schema": "merlin-ngspice-result/1",
            "engine": "ngspice",
            "netlist": validated,
            "log": combined[-100000:],
            "returncode": completed.returncode,
            "wall_seconds": elapsed,
            "limits": {"timeout_seconds": timeout_seconds,
                       "max_memory_bytes": max_memory_bytes},
            "resource_note": "wall-time enforced; memory limit is recorded but requires an OS/container supervisor",
        }
        encoded = (json.dumps(artifact, sort_keys=True, separators=(",", ":")) + "\n").encode()
        return {
            "artifact_bytes": encoded,
            "media_type": "application/vnd.merlin.ngspice-result+json",
            "summary": "ngspice batch analysis completed",
            "metadata": {"engine": "ngspice", "wall_seconds": elapsed,
                         "returncode": completed.returncode},
        }


def ngspice_task_executor(task: Mapping[str, Any], context: Any) -> dict[str, Any]:
    spec = task.get("experiment_spec")
    if not isinstance(spec, Mapping) or spec.get("engine") != "ngspice":
        raise ValueError("electrical task must declare engine=ngspice")
    budget = context.resource_budget
    timeout = min(600, int(budget.get("max_wall_seconds", 60)))
    context.emit_progress("Validating restricted ngspice netlist")
    context.emit_tool_event("agent.tool.started", "ngspice", {"task_id": context.task_id})
    result = run_ngspice(
        spec.get("netlist", ""),
        timeout_seconds=max(1, timeout),
        max_memory_bytes=min(8*1024*1024*1024, int(budget.get("memory_bytes", 1_073_741_824))),
    )
    context.emit_tool_event("agent.tool.completed", "ngspice", {"task_id": context.task_id})
    return result


__all__ = ["validate_netlist", "run_ngspice", "ngspice_task_executor"]
