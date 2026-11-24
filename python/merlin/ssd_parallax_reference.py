"""Bounded file-backed Parallax attention, one query/head and full visible KV.

This FP64 CPU research operator implements Algorithm 1 of arXiv:2605.29157v1,
referencing Yifei-Zuo/Parallax at 987102538da4c831a0b6f2dde03ce3251182a7cf.
See third_party/parallax/NOTICE and LICENSE. It is not the older scalar Merlin
local-linear sketch, a trained model, a GPU kernel, or a live mutable KV cache.

Storage is an immutable little-endian FP64 snapshot. A separately supplied
SHA-256 binds its shape and data. Verification and arithmetic share one payload
read; no output escapes before verification. Logical read-buffer limits do not
bound process RSS or the OS page cache and do not establish physical SSD I/O.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import hmac
import itertools
import math
import os
from pathlib import Path
import re
import stat
import struct
import tempfile

MAX_ROWS = 65536
MAX_DIM = 128
MAX_BUFFER_BYTES = 8 * 1024 * 1024
MAX_PAYLOAD_BYTES = 128 * 1024 * 1024
HEADER = struct.Struct("<8sIIII32s")
MAGIC = b"MRLKV001"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MISSING = object()


class KVStoreError(ValueError):
    """Invalid, changed, oversized or unverified snapshot; no result is valid."""


def _integer(value, label, maximum):
    if type(value) is not int or not 1 <= value <= maximum:
        raise KVStoreError(label + " must be a positive bounded integer")
    return value


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise KVStoreError(label + " must be a finite number, not a boolean")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise KVStoreError(label + " is outside FP64 range") from exc
    if not math.isfinite(result):
        raise KVStoreError(label + " must be finite")
    return result


def _vector(value, label, dimension=None):
    if not isinstance(value, (list, tuple)):
        raise KVStoreError(label + " must be a list or tuple")
    _integer(len(value), label + " dimension", MAX_DIM)
    if dimension is not None and len(value) != dimension:
        raise KVStoreError(label + " dimension mismatch")
    return tuple(_finite(x, label) for x in value)


def _checked(value):
    if not math.isfinite(value):
        raise KVStoreError("nonfinite intermediate or final attention arithmetic")
    return value


def _sum(terms):
    try:
        return _checked(math.fsum(terms))
    except (OverflowError, ValueError) as exc:
        raise KVStoreError("attention accumulation exceeded finite FP64 range") from exc


def _rows(keys, values):
    """Bounded validation without materializing outer iterables."""
    count = 0
    kd = vd = None
    for key, value in itertools.zip_longest(keys, values, fillvalue=_MISSING):
        if key is _MISSING or value is _MISSING:
            raise KVStoreError("key/value row counts differ")
        count += 1
        _integer(count, "row count", MAX_ROWS)
        key = _vector(key, "key", kd)
        value = _vector(value, "value", vd)
        kd, vd = len(key), len(value)
        if count * (kd + vd) * 8 > MAX_PAYLOAD_BYTES:
            raise KVStoreError("payload exceeds the fixed byte budget")
        yield key, value
    if not count:
        raise KVStoreError("at least one key/value row is required")


def _metadata(rows, kd, vd, payload_digest, file_digest):
    payload_bytes = rows * (kd + vd) * 8
    return {"schema": "merlin-kv-snapshot/1", "sha256": file_digest,
            "payload_sha256": payload_digest, "rows": rows,
            "key_dim": kd, "value_dim": vd, "dtype": "little-endian-float64",
            "payload_bytes": payload_bytes, "file_bytes": HEADER.size + payload_bytes}


def write_kv_store(path, keys, values):
    """Publish a new snapshot atomically without replacing an existing path.

    Parent directory must already exist. Rows may be generated incrementally.
    The private temporary file is fsynced and made owner-read-only before a hard
    link publishes it. Invalid inputs leave no final or temporary snapshot.
    This is local artifact creation, not a privileged filesystem boundary.
    """
    destination = Path(path)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("snapshot destination already exists")
    fd, temporary = tempfile.mkstemp(prefix=".merlin-kv-", dir=destination.parent)
    try:
        with os.fdopen(fd, "w+b") as output:
            output.write(bytes(HEADER.size))
            payload_hash = hashlib.sha256()
            count = 0
            for key, value in _rows(keys, values):
                count += 1
                kd, vd = len(key), len(value)
                encoded = struct.pack("<" + "d" * (kd + vd), *(key + value))
                output.write(encoded)
                payload_hash.update(encoded)
            header = HEADER.pack(MAGIC, 1, count, kd, vd, payload_hash.digest())
            output.seek(0)
            output.write(header)
            output.flush()
            os.fsync(output.fileno())
            output.seek(0)
            file_hash = hashlib.sha256()
            while data := output.read(65536):
                file_hash.update(data)
            os.fchmod(output.fileno(), stat.S_IRUSR)
            os.link(temporary, destination)
            result = _metadata(count, kd, vd, payload_hash.hexdigest(), file_hash.hexdigest())
        return result
    finally:
        # This owned random temporary path is never an input read or cleanup root.
        os.unlink(temporary)


def _signature(status):
    return (status.st_dev, status.st_ino, status.st_size,
            status.st_mtime_ns, status.st_ctime_ns)


class _Reader:
    def __init__(self, source, expected_sha256, block_records, max_buffer_bytes):
        if not isinstance(expected_sha256, str) or not _SHA256.fullmatch(expected_sha256):
            raise KVStoreError("a separately supplied lowercase SHA-256 is required")
        self.expected_sha256 = expected_sha256
        self.block_records = _integer(block_records, "block records", MAX_ROWS)
        self.max_buffer_bytes = _integer(max_buffer_bytes, "read buffer", MAX_BUFFER_BYTES)
        if max_buffer_bytes < HEADER.size:
            raise KVStoreError("read buffer cannot hold the fixed snapshot header")
        path = Path(source)
        if path.is_symlink():
            raise KVStoreError("snapshot symlinks are forbidden")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
        try:
            initial = os.fstat(fd)
            if not stat.S_ISREG(initial.st_mode):
                raise KVStoreError("snapshot must be a regular file")
            if not HEADER.size < initial.st_size <= HEADER.size + MAX_PAYLOAD_BYTES:
                raise KVStoreError("snapshot size is outside the fixed budget")
            self.initial_signature = _signature(initial)
            self.file = os.fdopen(fd, "rb", buffering=0)
        except BaseException:
            os.close(fd)
            raise
        try:
            header = self.file.read(HEADER.size)
            if len(header) != HEADER.size:
                raise KVStoreError("truncated snapshot header")
            magic, version, rows, kd, vd, payload_digest = HEADER.unpack(header)
            if magic != MAGIC or version != 1:
                raise KVStoreError("unsupported snapshot layout/version")
            self.rows = _integer(rows, "row count", MAX_ROWS)
            self.kd = _integer(kd, "key dimension", MAX_DIM)
            self.vd = _integer(vd, "value dimension", MAX_DIM)
            self.record = struct.Struct("<" + "d" * (kd + vd))
            self.payload_bytes = rows * self.record.size
            if self.payload_bytes > MAX_PAYLOAD_BYTES or initial.st_size != HEADER.size + self.payload_bytes:
                raise KVStoreError("snapshot shape/size mismatch, truncation or trailing data")
            self.read_size = min(rows, block_records) * self.record.size
            if self.read_size > max_buffer_bytes:
                raise KVStoreError("requested block exceeds the configured read buffer")
            self.expected_payload = payload_digest.hex()
            self.payload_hash = hashlib.sha256()
            self.file_hash = hashlib.sha256(header)
            self.io = {"bytes_read": HEADER.size, "payload_bytes_read": 0,
                       "read_calls": 1, "payload_passes": 1,
                       "peak_read_buffer_bytes": HEADER.size,
                       "configured_max_buffer_bytes": max_buffer_bytes,
                       "physical_ssd_io_measured": False, "page_cache_state": "uncontrolled"}
            self.verified = False
        except BaseException:
            self.file.close()
            raise

    def records(self):
        remaining = self.payload_bytes
        while remaining:
            requested = min(remaining, self.read_size)
            data = self.file.read(requested)
            if len(data) != requested:
                raise KVStoreError("snapshot changed or a payload read was incomplete")
            self.io["read_calls"] += 1
            self.io["bytes_read"] += len(data)
            self.io["payload_bytes_read"] += len(data)
            self.io["peak_read_buffer_bytes"] = max(self.io["peak_read_buffer_bytes"], len(data))
            self.payload_hash.update(data)
            self.file_hash.update(data)
            remaining -= len(data)
            for row in self.record.iter_unpack(data):
                if not all(math.isfinite(x) for x in row):
                    raise KVStoreError("nonfinite value in snapshot payload")
                yield row[:self.kd], row[self.kd:]
            # Release this raw buffer before allocating the next block.
            del data
        if not hmac.compare_digest(self.payload_hash.hexdigest(), self.expected_payload):
            raise KVStoreError("snapshot payload digest mismatch")
        if not hmac.compare_digest(self.file_hash.hexdigest(), self.expected_sha256):
            raise KVStoreError("snapshot identity digest mismatch")
        if _signature(os.fstat(self.file.fileno())) != self.initial_signature:
            raise KVStoreError("snapshot changed while it was being read")
        self.verified = True

    def metadata(self):
        if not self.verified:
            raise KVStoreError("snapshot verification did not finish")
        return _metadata(self.rows, self.kd, self.vd, self.expected_payload,
                         self.file_hash.hexdigest())


@contextmanager
def _reader(path, expected_sha256, block_records, max_buffer_bytes):
    reader = _Reader(path, expected_sha256, block_records, max_buffer_bytes)
    try:
        yield reader
    finally:
        reader.file.close()


def load_kv_store(path, *, expected_sha256):
    """Resident comparison path; intentionally materializes the complete KV."""
    with _reader(path, expected_sha256, 64, MAX_BUFFER_BYTES) as reader:
        keys, values = [], []
        for key, value in reader.records():
            keys.append(key)
            values.append(value)
        return {"keys": tuple(keys), "values": tuple(values),
                "store": reader.metadata(), "io": dict(reader.io)}


def _inputs(q, r, kd, qk_scale):
    q, r = _vector(q, "query", kd), _vector(r, "probe", kd)
    scale = 1.0 / math.sqrt(kd) if qk_scale is None else _finite(qk_scale, "QK scale")
    if scale <= 0:
        raise KVStoreError("QK scale must be positive")
    return q, r, scale


def _scores(q, r, key, origin, scale):
    # A common K translation changes logits by a constant and cancels from
    # the probe covariance. Center first to reduce large-offset cancellation.
    delta = tuple(_checked(k - base) for k, base in zip(key, origin))
    score = _checked(_sum(_checked(a * b) for a, b in zip(q, delta)) * scale)
    probe = _sum(_checked(a * b) for a, b in zip(r, delta))
    return score, probe


def _result(output, rows, kd, vd, scale):
    return {"schema": "merlin-parallax-snapshot-attention/1", "output": output,
            "rows": rows, "key_dim": kd, "value_dim": vd, "qk_scale": scale,
            "one_query_one_head_full_kv": True, "arithmetic": "CPU-FP64",
            "trained_model_executed": False, "gpu_executed": False,
            "production_qualified": False}


def parallax_attention_resident(q, r, keys, values, *, qk_scale=None):
    """Resident normalized-probability/covariance comparison implementation."""
    resident = tuple(_rows(keys, values))
    kd, vd = len(resident[0][0]), len(resident[0][1])
    q, r, scale = _inputs(q, r, kd, qk_scale)
    origin, value_origin = resident[0]
    scores = tuple(_scores(q, r, key, origin, scale) for key, _ in resident)
    maximum = max(score for score, _ in scores)
    weights = tuple(math.exp(score - maximum) for score, _ in scores)
    denominator = _sum(weights)
    probabilities = tuple(weight / denominator for weight in weights)
    mean_probe = _sum(p * score[1] for p, score in zip(probabilities, scores))
    output = []
    for column in range(vd):
        centered = tuple(_checked(value[column] - value_origin[column]) for _, value in resident)
        mean = _sum(p * v for p, v in zip(probabilities, centered))
        covariance = _sum(_checked(p * _checked(score[1] - mean_probe) * _checked(v - mean))
                          for p, score, v in zip(probabilities, scores, centered))
        output.append(_checked(value_origin[column] + _checked(mean - covariance)))
    return _result(output, len(resident), kd, vd, scale)


def parallax_attention_file(path, q, r, *, expected_sha256, qk_scale=None,
                            block_records=64, max_buffer_bytes=MAX_BUFFER_BYTES):
    """One verified file pass with online, shared Parallax sufficient statistics.

    Both accumulator branches consume the SAME KV block. A changed maximum
    rescales all four moment accumulators together. R is signed and unscaled.
    K and V are centered on the first row, an exact translation identity that
    reduces cancellation; ordinary finite-precision limits still apply.
    """
    with _reader(path, expected_sha256, block_records, max_buffer_bytes) as reader:
        q, r, scale = _inputs(q, r, reader.kd, qk_scale)
        origin = value_origin = None
        maximum = -math.inf
        d1 = d2 = 0.0
        o1, o2 = [0.0] * reader.vd, [0.0] * reader.vd
        for key, value in reader.records():
            if origin is None:
                origin, value_origin = key, value
            score, probe = _scores(q, r, key, origin, scale)
            next_maximum = max(maximum, score)
            rescale = math.exp(maximum - next_maximum)
            weight = math.exp(score - next_maximum)
            probe_weight = _checked(weight * probe)
            d1 = _checked(d1 * rescale + weight)
            d2 = _checked(d2 * rescale + probe_weight)
            for column in range(reader.vd):
                centered = _checked(value[column] - value_origin[column])
                o1[column] = _checked(o1[column] * rescale + weight * centered)
                o2[column] = _checked(o2[column] * rescale + probe_weight * centered)
            maximum = next_maximum
        store = reader.metadata()  # Withhold output until the read verifies.
        output = [_checked(value_origin[i] + _checked(
                    _checked(o1[i] / d1) * _checked(1.0 + d2 / d1) - o2[i] / d1))
                  for i in range(reader.vd)]
        result = _result(output, reader.rows, reader.kd, reader.vd, scale)
        result.update({"store": store, "io": dict(reader.io)})
        return result
