"""Prepared, exact tensor workloads for repeated Merlin simulations."""
from collections import defaultdict
from dataclasses import dataclass
from itertools import repeat

from .studio_tensor_backend import validate_jobs
from .studio_tensor_tile import IDENTITY, LIMIT


@dataclass(frozen=True)
class _Group:
    count: int
    length: int
    operands: bytes
    left: bytes
    right: bytes
    output_rows: tuple


@dataclass(frozen=True)
class PreparedTensorJobs:
    size: int
    groups: tuple[_Group, ...]

    def execute(self):
        """Run all arithmetic afresh. Prepared buffers are immutable snapshots."""
        import numpy as np

        values = [None] * self.size

        def valid_range(real, imag):
            return (real >= -LIMIT) & (real < LIMIT) & (imag >= -LIMIT) & (imag < LIMIT)

        def multiply(ar, ai, br, bi):
            return ar @ br - ai @ bi, ar @ bi + ai @ br

        for group in self.groups:
            packed = np.frombuffer(group.operands, dtype=np.int64).reshape(
                group.length, 2, group.count, 2, 2)
            real = np.broadcast_to(np.eye(2, dtype=np.int64), (group.count, 2, 2))
            imag = np.zeros_like(real)
            valid = np.ones(group.count, dtype=bool)
            for item in packed:
                real, imag = multiply(real, imag, item[0], item[1])
                valid &= valid_range(real, imag).all(axis=(1, 2))
                # Keep the first narrowing fault, even when a later matrix is zero.
                real = np.where(valid[:, None, None], real, 0)
                imag = np.where(valid[:, None, None], imag, 0)
            if group.left:
                left = np.frombuffer(group.left, dtype=np.int64).reshape(2, group.count, 1, 2)
                right = np.frombuffer(group.right, dtype=np.int64).reshape(2, group.count, 2, 1)
                real, imag = multiply(left[0], left[1], real, imag)
                real, imag = multiply(real, imag, right[0], right[1])
                real, imag = real[:, 0, 0], imag[:, 0, 0]
            else:
                real, imag = (np.trace(a, axis1=1, axis2=2) for a in (real, imag))
            valid &= valid_range(real, imag)
            for index, rows in enumerate(group.output_rows):
                if valid[index]:
                    value = int(real[index]), int(imag[index])
                    for row in rows:
                        values[row] = value
        return values


def prepare_jobs(jobs, *, layout="grouped"):
    """Validate every job before snapshotting or merging equivalent inputs."""
    import numpy as np

    if layout not in ("grouped", "padded", "deduplicated"):
        raise ValueError("Unknown prepared tensor layout.")
    validate_jobs(jobs)
    groups = defaultdict(list)
    if layout == "deduplicated":
        unique = {}
        for index, (chain, boundary) in enumerate(jobs):
            unique.setdefault((tuple(chain), boundary), []).append(index)
        entries = ((chain, boundary, rows) for (chain, boundary), rows in unique.items())
    else:
        entries = ((chain, boundary, [index]) for index, (chain, boundary) in enumerate(jobs))
    for chain, boundary, rows in entries:
        groups[boundary.mode, 0 if layout == "padded" else len(chain)].append((chain, boundary, rows))

    packed_groups = []
    for (mode, _), group in groups.items():
        length = max(len(chain) for chain, _, _ in group)
        matrices = [tuple(chain) + tuple(repeat(IDENTITY, length-len(chain))) for chain, _, _ in group]
        operands = np.asarray(matrices, dtype=np.int64).transpose(1, 4, 0, 2, 3).tobytes()

        def encode_vectors(side):
            return np.asarray([getattr(boundary, side) for _, boundary, _ in group],
                              dtype=np.int64).transpose(2, 0, 1).tobytes()

        packed_groups.append(_Group(
            len(group), length, operands,
            encode_vectors("left") if mode == "open" else b"",
            encode_vectors("right") if mode == "open" else b"",
            tuple(tuple(rows) for _, _, rows in group),
        ))
    return PreparedTensorJobs(len(jobs), tuple(packed_groups))
