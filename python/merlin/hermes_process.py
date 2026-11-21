"""Typed host-owned limits for fixed tools; no cooperative sandbox fallback."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
import re
import stat


class ProcessIsolationUnavailable(RuntimeError):
    """The separately provisioned host isolation mechanism is unavailable."""


@dataclass(frozen=True)
class ProcessLimits:
    memory_bytes: int = 64 * 1024 * 1024
    cpu_seconds: int = 2
    wall_seconds: float = 5.0
    cpu_cores: int = 1
    output_bytes: int = 128 * 1024

    def validate(self):
        for key, lo, hi in (("memory_bytes", 32 * 1024 * 1024, 4 * 1024**3),
                            ("cpu_seconds", 1, 60), ("cpu_cores", 1, 8),
                            ("output_bytes", 2048, 1024 * 1024)):
            value = getattr(self, key)
            if type(value) is not int or not lo <= value <= hi:
                raise ValueError("bounded integer process limit required: " + key)
        if (type(self.wall_seconds) not in (int, float) or not math.isfinite(self.wall_seconds)
                or not 0.05 <= self.wall_seconds <= 120
                or self.cpu_seconds > math.ceil(self.cpu_cores * self.wall_seconds)):
            raise ValueError("finite compatible wall and CPU limits required")


def read_fixed_program(path, expected: str) -> bytes:
    """Hash the exact bytes to execute; refuse final symlink and nonregular files."""
    path = Path(path)
    if not path.is_absolute() or not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
        raise ValueError('absolute fixed program and SHA-256 required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('regular fixed program required')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(1024 * 1024 + 1)
    finally:
        os.close(fd)
    if len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('fixed program identity differs')
    return raw
