"""Provenance policy for synthetic Wilborn prototypes.

This module cannot certify a record as real. Production classification must be
assigned by a trusted ingestion service, not by AI or user-provided payloads.
"""
from dataclasses import dataclass
from enum import Enum

class DataClass(str, Enum):
    SYNTHETIC = "synthetic"
    REAL = "real"

@dataclass(frozen=True)
class Provenance:
    classification: DataClass
    environment: str
    source: str
    verified: bool = False

    def __post_init__(self):
        if not self.source or not self.source.strip():
            raise ValueError("source required")
        if self.environment not in ("demo", "production"):
            raise ValueError("unknown environment")
        if self.environment == "demo" and self.classification != DataClass.SYNTHETIC:
            raise ValueError("real data prohibited in demo")
        if self.environment == "production" and self.classification != DataClass.REAL:
            raise ValueError("synthetic data prohibited in production")
        if self.classification == DataClass.REAL and not self.verified:
            raise ValueError("real data requires trusted verification")

def assert_demo(provenance):
    if not isinstance(provenance, Provenance):
        raise PermissionError("provenance missing")
    if provenance != Provenance(DataClass.SYNTHETIC, "demo", provenance.source, False):
        raise PermissionError("demo-only operation")
    return True

def response_envelope(payload, provenance):
    assert_demo(provenance)
    return {"data_class": "synthetic", "environment": "demo",
            "source": provenance.source, "verified_real": False, "data": payload}
