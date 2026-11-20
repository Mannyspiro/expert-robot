"""Experimental batch execution of the exact Merlin tensor tile."""
from collections import defaultdict
from importlib.util import find_spec
from itertools import product

from .studio_tensor_tile import IDENTITY, LIMIT, ZERO, add, check, mul, run, validate_matrix

MAX_BATCH = 1024
# Selected on tuning seed 410 and checked on a separate workload.
VECTOR_MIN_BATCH = 128


def validate_jobs(jobs):
    if not 1 <= len(jobs) <= MAX_BATCH:
        raise ValueError(f"Expected 1 to {MAX_BATCH} independent tensor jobs.")
    for chain, boundary in jobs:
        if not 1 <= len(chain) <= 8:
            raise ValueError("Expected one to eight matrices per tensor job.")
        boundary.validate()
        for matrix in chain:
            validate_matrix(matrix)


def _reference(chain, boundary):
    return run(chain, boundary)[0]


def _scalar(chain, boundary):
    state = IDENTITY
    for matrix in chain:
        state = tuple(tuple(check(add(
            mul(state[i][0], matrix[0][j]), mul(state[i][1], matrix[1][j]),
        )) for j in range(2)) for i in range(2))
    if boundary.mode == "loop":
        return check(add(state[0][0], state[1][1]))
    total = ZERO
    for i, j in product(range(2), repeat=2):
        total = add(total, mul(mul(boundary.left[i], state[i][j]), boundary.right[j]))
    return check(total)


def _row_results(execute, jobs):
    values = []
    for chain, boundary in jobs:
        try:
            values.append(execute(chain, boundary))
        except OverflowError:
            values.append(None)
    return values


def _vector(jobs):
    import numpy as np

    def complex_dot(ar, ai, br, bi):
        return ar @ br - ai @ bi, ar @ bi + ai @ br

    def within(real, imag):
        return (real >= -LIMIT) & (real < LIMIT) & (imag >= -LIMIT) & (imag < LIMIT)

    groups = defaultdict(list)
    for index, (chain, boundary) in enumerate(jobs):
        groups[len(chain), boundary.mode].append((index, chain, boundary))
    values = [None] * len(jobs)
    for (length, mode), group in groups.items():
        packed = np.asarray([chain for _, chain, _ in group], dtype=np.int64)
        # Checked 16-bit operands bound contract components by 2**32. The
        # four-term three-factor readout fits within 2**51 before narrowing.
        real = np.broadcast_to(np.eye(2, dtype=np.int64), (len(group), 2, 2))
        imag = np.zeros_like(real)
        valid = np.ones(len(group), dtype=bool)
        for i in range(length):
            real, imag = complex_dot(real, imag, packed[:, i, :, :, 0], packed[:, i, :, :, 1])
            valid &= within(real, imag).all(axis=(1, 2))
            real = np.where(valid[:, None, None], real, 0)
            imag = np.where(valid[:, None, None], imag, 0)
        if mode == "loop":
            answer_r, answer_i = (np.trace(a, axis1=1, axis2=2) for a in (real, imag))
        else:
            left = np.asarray([boundary.left for _, _, boundary in group], dtype=np.int64)
            right = np.asarray([boundary.right for _, _, boundary in group], dtype=np.int64)
            real, imag = complex_dot(left[:, None, :, 0], left[:, None, :, 1], real, imag)
            answer_r, answer_i = complex_dot(real, imag, right[:, :, None, 0], right[:, :, None, 1])
            answer_r, answer_i = answer_r[:, 0, 0], answer_i[:, 0, 0]
        valid &= within(answer_r, answer_i)
        for i, (index, _, _) in enumerate(group):
            if valid[i]:
                values[index] = int(answer_r[i]), int(answer_i[i])
    return values


def choose_backend(count):
    return "vector" if count >= VECTOR_MIN_BATCH and find_spec("numpy") else "scalar"


def execute_jobs(jobs, *, backend="auto"):
    """Return one exact value or overflow marker per job, in caller order.

    The original single-job engine remains the source of step-by-step traces.
    """
    validate_jobs(jobs)
    if backend == "auto":
        backend = choose_backend(len(jobs))
    if backend == "reference":
        return _row_results(_reference, jobs)
    if backend == "scalar":
        return _row_results(_scalar, jobs)
    if backend == "vector":
        return _vector(jobs)
    raise ValueError("Unknown tensor backend.")


def studio_tensor_jobs(count):
    """Generate the actual open and periodic Model Lab workload."""
    if type(count) is not int or not 1 <= count <= MAX_BATCH:
        raise ValueError(f"Expected an integer batch size from 1 to {MAX_BATCH}.")
    from .studio_tensor_tile import Boundary, ONE, pair_from

    chain = (pair_from([[1, 1], [0, 1]]), pair_from([[1, 0], [1, 1]]))
    open_job = chain, Boundary("open", (ONE, ZERO), (ZERO, ONE))
    loop_job = chain, Boundary("loop")
    return tuple(open_job if i % 2 == 0 else loop_job for i in range(count))
