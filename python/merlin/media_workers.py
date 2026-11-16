"""Bounded, provenance-producing media workers for Merlin.

These adapters are deliberately not wired into the public API by default.
They execute only after an operator supplies an explicitly configured,
loopback ComfyUI endpoint or an absolute Blender executable. A successful
execution receipt records bytes and tool identity; it is not a CACE attestation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


MAX_WORKFLOW_BYTES = 1_000_000
MAX_WORKFLOW_NODES = 500
MAX_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_LOG_BYTES = 256 * 1024
JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class MediaWorkerError(RuntimeError):
    """A bounded media worker could not complete its requested operation."""


@dataclass(frozen=True)
class MediaExecutionReceipt:
    schema: str
    worker: str
    status: str
    tool_version: str | None
    job_id: str
    started_at: float
    finished_at: float
    duration_ms: int
    input_sha256: str
    outputs: tuple[dict[str, Any], ...]
    log: str
    resource: dict[str, Any]
    authority: str = "execution_only"
    independently_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _loopback_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in
            {"127.0.0.1", "localhost", "::1"} or parsed.username or
            parsed.password or parsed.query or parsed.fragment):
        raise ValueError("media worker endpoint must be an HTTP loopback URL")
    return value.rstrip("/")


def _safe_output_dir(value: str | Path) -> Path:
    root = Path(value).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not root.is_dir():
        raise ValueError("output path must be a directory")
    return root


def _read_bounded(response: Any, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(min(64 * 1024, limit + 1 - total))
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise MediaWorkerError("worker response exceeded the configured byte limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _http_json(base_url: str, path: str, *, method: str = "GET",
               payload: Mapping[str, Any] | None = None,
               timeout: float = 5.0) -> dict[str, Any]:
    body = None if payload is None else json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    request = Request(base_url + path, data=body, method=method,
                      headers={"Accept": "application/json",
                               "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = _read_bounded(response, 2 * 1024 * 1024)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise MediaWorkerError(f"ComfyUI request failed: {type(exc).__name__}") from exc
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MediaWorkerError("ComfyUI returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise MediaWorkerError("ComfyUI response must be a JSON object")
    return result


def _download_output(base_url: str, file_row: Mapping[str, Any],
                     output_dir: Path, byte_limit: int) -> dict[str, Any]:
    filename = file_row.get("filename") or file_row.get("name")
    subfolder = file_row.get("subfolder", "")
    file_type = file_row.get("type", "output")
    if (not isinstance(filename, str) or not filename or
            Path(filename).name != filename or filename in {".", ".."}):
        raise MediaWorkerError("ComfyUI returned an unsafe output filename")
    if not isinstance(subfolder, str) or Path(subfolder).is_absolute() or ".." in Path(subfolder).parts:
        raise MediaWorkerError("ComfyUI returned an unsafe output subfolder")
    if file_type not in {"output", "temp", "input"}:
        raise MediaWorkerError("ComfyUI returned an unsupported output type")
    query = urlencode({"filename": filename, "subfolder": subfolder, "type": file_type})
    request = Request(base_url + "/view?" + query, headers={"Accept": "application/octet-stream"})
    try:
        with urlopen(request, timeout=10.0) as response:
            content = _read_bounded(response, byte_limit)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise MediaWorkerError(f"ComfyUI output retrieval failed: {type(exc).__name__}") from exc
    if not content:
        raise MediaWorkerError("ComfyUI returned an empty output")
    target = output_dir / filename
    if target.exists():
        raise MediaWorkerError("output filename collision; refusing to overwrite an artifact")
    target.write_bytes(content)
    return {"path": str(target), "filename": filename, "size_bytes": len(content),
            "media_sha256": sha256(content).hexdigest()}


class ComfyUIWorker:
    """Submit one bounded workflow to a loopback ComfyUI server and collect outputs."""

    def __init__(self, base_url: str, output_dir: str | Path, *,
                 timeout_seconds: float = 300.0, poll_seconds: float = 0.5,
                 max_output_bytes: int = MAX_OUTPUT_BYTES,
                 clock: Callable[[], float] = time.monotonic,
                 sleeper: Callable[[float], None] = time.sleep):
        self.base_url = _loopback_base_url(base_url)
        self.output_dir = _safe_output_dir(output_dir)
        if not 1 <= timeout_seconds <= 3600 or not 0.05 <= poll_seconds <= 10:
            raise ValueError("ComfyUI timeout or polling interval is outside policy")
        if not 1 <= max_output_bytes <= MAX_OUTPUT_BYTES:
            raise ValueError("ComfyUI output limit is outside policy")
        self.timeout_seconds = timeout_seconds
        self.poll_seconds = poll_seconds
        self.max_output_bytes = max_output_bytes
        self.clock = clock
        self.sleeper = sleeper

    def execute(self, workflow: Mapping[str, Any], *, cancel: Any = None) -> MediaExecutionReceipt:
        if not isinstance(workflow, Mapping) or not workflow:
            raise ValueError("workflow must be a non-empty object")
        encoded = json.dumps(workflow, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode("utf-8")
        if len(encoded) > MAX_WORKFLOW_BYTES:
            raise ValueError("workflow exceeds the configured request limit")
        if len(workflow) > MAX_WORKFLOW_NODES:
            raise ValueError("workflow exceeds the configured node limit")
        input_digest = sha256(encoded).hexdigest()
        started = time.time()
        deadline = self.clock() + self.timeout_seconds
        submission = _http_json(self.base_url, "/prompt", method="POST",
                                payload={"prompt": workflow}, timeout=10.0)
        job_id = submission.get("prompt_id") or submission.get("job_id")
        if not isinstance(job_id, str) or not JOB_ID_RE.fullmatch(job_id):
            raise MediaWorkerError("ComfyUI did not return a valid job identifier")
        log_rows: list[str] = []
        while True:
            if cancel is not None and cancel.is_set():
                try:
                    _http_json(self.base_url, f"/api/jobs/{job_id}/cancel",
                               method="POST", payload={}, timeout=3.0)
                finally:
                    raise MediaWorkerError("ComfyUI job cancelled")
            if self.clock() >= deadline:
                try:
                    _http_json(self.base_url, f"/api/jobs/{job_id}/cancel",
                               method="POST", payload={}, timeout=3.0)
                except MediaWorkerError:
                    pass
                raise MediaWorkerError("ComfyUI job exceeded its execution deadline")
            state = _http_json(self.base_url, f"/api/jobs/{job_id}", timeout=5.0)
            status = str(state.get("status", "")).lower()
            log_rows.append(f"job={job_id} status={status or 'unknown'}")
            if status in {"failed", "error"}:
                raise MediaWorkerError("ComfyUI job failed")
            if status in {"completed", "success", "succeeded"}:
                break
            if status in {"cancelled", "canceled"}:
                raise MediaWorkerError("ComfyUI job was cancelled")
            self.sleeper(min(self.poll_seconds, max(0.0, deadline - self.clock())))
        rows = state.get("outputs")
        # ComfyUI's jobs API groups outputs by node and media type.
        flattened: list[Mapping[str, Any]] = []
        if isinstance(rows, dict):
            for node_output in rows.values():
                if not isinstance(node_output, dict):
                    continue
                for media_type in ("images", "video", "audio", "3d"):
                    entries = node_output.get(media_type, [])
                    if isinstance(entries, list):
                        flattened.extend(entry for entry in entries if isinstance(entry, Mapping))
        elif isinstance(rows, list):
            flattened.extend(entry for entry in rows if isinstance(entry, Mapping))
        if not flattened:
            raise MediaWorkerError("ComfyUI completed without output files")
        if len(flattened) > 32:
            raise MediaWorkerError("ComfyUI returned more than 32 output files")
        collected: list[dict[str, Any]] = []
        total = 0
        try:
            for row in flattened:
                remaining = self.max_output_bytes - total
                if remaining <= 0:
                    raise MediaWorkerError("ComfyUI outputs exceed the configured aggregate byte limit")
                item = _download_output(self.base_url, row, self.output_dir, remaining)
                collected.append(item)
                total += item["size_bytes"]
        except Exception:
            for item in collected:
                Path(item["path"]).unlink(missing_ok=True)
            raise
        outputs = tuple(collected)
        if not outputs:
            raise MediaWorkerError("ComfyUI completed without retrievable output files")
        finished = time.time()
        return MediaExecutionReceipt(
            schema="merlin-media-execution/1", worker="comfyui",
            status="completed", tool_version=state.get("version"),
            job_id=job_id, started_at=started, finished_at=finished,
            duration_ms=max(0, int((finished - started) * 1000)),
            input_sha256=input_digest, outputs=outputs,
            log="\n".join(log_rows)[-MAX_LOG_BYTES:],
            resource={"reported": state.get("resource") or state.get("system_stats"),
                      "telemetry_source": "ComfyUI job response"},
        )


class BlenderWorker:
    """Run a bounded headless render without a shell or arbitrary command string."""

    def __init__(self, executable: str | Path, workspace: str | Path, *,
                 timeout_seconds: float = 300.0,
                 max_output_bytes: int = MAX_OUTPUT_BYTES):
        self.executable = Path(executable).expanduser().resolve()
        self.workspace = Path(workspace).expanduser().resolve()
        if not self.executable.is_absolute() or not self.executable.is_file():
            raise ValueError("Blender executable must be an existing absolute file")
        if not os.access(self.executable, os.X_OK):
            raise ValueError("Blender executable is not executable")
        if not self.workspace.is_dir():
            raise ValueError("Blender workspace must be an existing directory")
        if not 1 <= timeout_seconds <= 3600:
            raise ValueError("Blender timeout is outside policy")
        if not 1 <= max_output_bytes <= MAX_OUTPUT_BYTES:
            raise ValueError("Blender output limit is outside policy")
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes

    def execute(self, scene: str | Path, output_dir: str | Path, *,
                frame: int = 1, resolution_scale: int = 25) -> MediaExecutionReceipt:
        scene_path = Path(scene).expanduser().resolve()
        out_dir = Path(output_dir).expanduser().resolve()
        try:
            scene_path.relative_to(self.workspace)
            out_dir.relative_to(self.workspace)
        except ValueError as exc:
            raise ValueError("scene and output directory must remain inside the worker workspace") from exc
        out_dir.mkdir(parents=True, exist_ok=True)
        if not out_dir.is_dir():
            raise ValueError("Blender output path must be a directory")
        if not scene_path.is_file() or scene_path.suffix.lower() != ".blend":
            raise ValueError("scene must be an existing .blend file")
        if not isinstance(frame, int) or not 1 <= frame <= 100000:
            raise ValueError("frame is outside policy")
        if not isinstance(resolution_scale, int) or not 1 <= resolution_scale <= 100:
            raise ValueError("resolution scale is outside policy")
        scene_bytes = scene_path.read_bytes()
        if len(scene_bytes) > MAX_OUTPUT_BYTES:
            raise ValueError("scene file exceeds the configured input limit")
        input_digest = sha256(scene_bytes).hexdigest()
        output_prefix = out_dir / "merlin-frame-"
        render_setup = (
            "import bpy; "
            "s=bpy.context.scene; "
            "s.render.resolution_x=64; "
            "s.render.resolution_y=64; "
            f"s.render.resolution_percentage={resolution_scale}"
        )
        argv = [str(self.executable), "--background", str(scene_path),
                "--python-expr", render_setup,
                "--render-output", str(output_prefix), "--render-format", "PNG",
                "--render-frame", str(frame)]
        version = None
        try:
            version_probe = subprocess.run(
                [str(self.executable), "--version"], cwd=str(self.workspace),
                shell=False, check=False, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=10,
            )
            if version_probe.returncode == 0:
                version = (version_probe.stdout or b"").decode("utf-8", errors="replace").strip()[:200]
        except (OSError, subprocess.TimeoutExpired):
            version = None
        started = time.time()
        monotonic_start = time.monotonic()
        try:
            completed = subprocess.run(
                argv, cwd=str(self.workspace), shell=False, check=False,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=self.timeout_seconds,
                env={**os.environ, "BLENDER_USER_CONFIG": str(self.workspace / ".blender-config"),
                     "BLENDER_USER_SCRIPTS": str(self.workspace / ".blender-scripts")},
            )
        except subprocess.TimeoutExpired as exc:
            raise MediaWorkerError("Blender render exceeded its execution deadline") from exc
        except OSError as exc:
            raise MediaWorkerError(f"Blender execution failed: {type(exc).__name__}") from exc
        log = (completed.stdout or b"")[-MAX_LOG_BYTES:].decode("utf-8", errors="replace")
        if completed.returncode != 0:
            raise MediaWorkerError(f"Blender exited with status {completed.returncode}: {log[-1000:]}")
        candidates = sorted(out_dir.glob("merlin-frame-*.png"))
        if not candidates:
            raise MediaWorkerError("Blender completed without producing a PNG frame")
        outputs = []
        total = 0
        for path in candidates:
            content = path.read_bytes()
            total += len(content)
            outputs.append({"path": str(path), "filename": path.name,
                            "size_bytes": len(content),
                            "media_sha256": sha256(content).hexdigest()})
        if total > self.max_output_bytes:
            for row in outputs:
                Path(row["path"]).unlink(missing_ok=True)
            raise MediaWorkerError("Blender outputs exceed the configured aggregate byte limit")
        finished = time.time()
        return MediaExecutionReceipt(
            schema="merlin-media-execution/1", worker="blender",
            status="completed", tool_version=version, job_id=input_digest[:24],
            started_at=started, finished_at=finished,
            duration_ms=max(0, int((time.monotonic() - monotonic_start) * 1000)),
            input_sha256=input_digest, outputs=tuple(outputs), log=log,
            resource={"timeout_seconds": self.timeout_seconds,
                      "telemetry_source": "host process runtime; detailed CPU/GPU metrics unavailable"},
        )
