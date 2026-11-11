"""Evidence-bound RSI induction, immutable lineage, and research metadata.

This module is deliberately fail-closed:
* external records require a trusted Ed25519 receipt;
* candidate/evaluation events are append-only and hash chained;
* CACE verification and human promotion approval are separate receipts;
* optional optimizer adapters are advisory until paired held-out evidence wins.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import base64
import hashlib
import json
import math
import sqlite3
import statistics
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable, Mapping


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("receipt timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class SignedReceipt:
    schema_version: int
    issuer: str
    key_id: str
    issued_at: str
    claims: Mapping[str, Any]
    signature_b64: str

    def unsigned_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "issuer": self.issuer,
            "key_id": self.key_id,
            "issued_at": self.issued_at,
            "claims": dict(self.claims),
        }

    @property
    def receipt_digest(self) -> str:
        return sha256_hex(canonical_json({**self.unsigned_payload(), "signature_b64": self.signature_b64}))


def verify_signed_receipt(
    receipt: SignedReceipt,
    trusted_keys: Mapping[str, str],
    *,
    expected_issuer: str | None = None,
    expected_claims: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    max_age: timedelta = timedelta(days=7),
    verifier: Callable[[bytes, bytes, str], bool] | None = None,
) -> bool:
    """Verify Ed25519 over canonical JSON. trusted_keys maps key_id to PEM public key."""
    if receipt.schema_version != 1 or not receipt.issuer or not receipt.key_id:
        return False
    if expected_issuer is not None and receipt.issuer != expected_issuer:
        return False
    pem = trusted_keys.get(receipt.key_id)
    if not pem:
        return False
    try:
        issued = _parse_time(receipt.issued_at)
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if issued > current + timedelta(minutes=5) or current - issued > max_age:
            return False
        if expected_claims and any(receipt.claims.get(k) != v for k, v in expected_claims.items()):
            return False
        signature = base64.b64decode(receipt.signature_b64, validate=True)
        payload = canonical_json(receipt.unsigned_payload())
        if verifier is not None:
            return bool(verifier(payload, signature, pem))
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        key = serialization.load_pem_public_key(pem.encode("utf-8"))
        if not isinstance(key, Ed25519PublicKey):
            return False
        key.verify(signature, payload)
        return True
    except Exception:
        return False


class AppendOnlyLedger:
    """SQLite event ledger with immutable rows and a verifiable SHA-256 chain."""

    def __init__(self, database: str | Path):
        self.database = str(database)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS rsi_events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS rsi_events_no_update
                BEFORE UPDATE ON rsi_events BEGIN SELECT RAISE(ABORT, 'append-only ledger'); END;
                CREATE TRIGGER IF NOT EXISTS rsi_events_no_delete
                BEFORE DELETE ON rsi_events BEGIN SELECT RAISE(ABORT, 'append-only ledger'); END;
            """)

    def _connect(self):
        db = sqlite3.connect(self.database)
        db.row_factory = sqlite3.Row
        return db

    def append(self, event_type: str, entity_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not event_type or not entity_id:
            raise ValueError("event_type and entity_id are required")
        payload_json = canonical_json(dict(payload)).decode("utf-8")
        payload_hash = sha256_hex(payload_json.encode("utf-8"))
        with self._connect() as db:
            last = db.execute("SELECT event_hash FROM rsi_events ORDER BY seq DESC LIMIT 1").fetchone()
            previous = last["event_hash"] if last else "0" * 64
            created = datetime.now(timezone.utc).isoformat()
            material = {
                "event_type": event_type, "entity_id": entity_id,
                "payload_sha256": payload_hash, "previous_hash": previous,
                "created_at": created,
            }
            event_hash = sha256_hex(canonical_json(material))
            event_id = event_hash[:32]
            cur = db.execute(
                """INSERT INTO rsi_events
                   (event_id,event_type,entity_id,payload_json,payload_sha256,previous_hash,event_hash,created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (event_id,event_type,entity_id,payload_json,payload_hash,previous,event_hash,created),
            )
            return {"seq": cur.lastrowid, "event_id": event_id, "event_hash": event_hash}

    def record_candidate(
        self, *, candidate_id: str, parent_candidate_id: str | None,
        source_receipt: SignedReceipt, artifact_sha256: str,
        generator: str, mutation: Mapping[str, Any],
    ) -> dict[str, Any]:
        if len(artifact_sha256) != 64 or any(c not in "0123456789abcdef" for c in artifact_sha256):
            raise ValueError("artifact_sha256 must be lowercase SHA-256")
        if not candidate_id or not generator:
            raise ValueError("candidate_id and generator are required")
        return self.append("candidate.created", candidate_id, {
            "candidate_id": candidate_id, "parent_candidate_id": parent_candidate_id,
            "source_receipt_digest": source_receipt.receipt_digest,
            "source_claims": dict(source_receipt.claims), "artifact_sha256": artifact_sha256,
            "generator": generator, "mutation": dict(mutation),
        })

    def record_evaluation(self, *, candidate_id: str, suite_sha256: str,
                          metrics: Mapping[str, float], passed: bool,
                          evaluator_receipt_digest: str) -> dict[str, Any]:
        if len(suite_sha256) != 64 or not evaluator_receipt_digest:
            raise ValueError("suite digest and evaluator receipt are required")
        normalized = {str(k): float(v) for k,v in metrics.items()}
        if any(not math.isfinite(v) for v in normalized.values()):
            raise ValueError("evaluation metrics must be finite")
        return self.append("candidate.evaluated", candidate_id, {
            "candidate_id": candidate_id, "suite_sha256": suite_sha256,
            "metrics": normalized, "passed": bool(passed),
            "evaluator_receipt_digest": evaluator_receipt_digest,
        })

    def record_cace_verification(self, *, candidate_id: str, receipt: SignedReceipt,
                                 trusted_keys: Mapping[str, str], artifact_sha256: str,
                                 suite_sha256: str, verifier=None) -> dict[str, Any]:
        expected = {"candidate_id": candidate_id, "candidate_digest": artifact_sha256,
                    "benchmark_manifest_sha256": suite_sha256, "status": "pass",
                    "authority": "verification-only"}
        if not verify_signed_receipt(receipt, trusted_keys, expected_issuer="cace", 
                                     expected_claims=expected, verifier=verifier):
            raise PermissionError("independent CACE receipt is missing, untrusted, stale, or mismatched")
        return self.append("candidate.cace_verified", candidate_id, {
            "candidate_id": candidate_id, "artifact_sha256": artifact_sha256,
            "suite_sha256": suite_sha256, "receipt_digest": receipt.receipt_digest,
            "issuer": receipt.issuer, "key_id": receipt.key_id,
        })

    def record_promotion(self, *, candidate_id: str, artifact_sha256: str,
                         cace_receipt: SignedReceipt, approval_receipt: SignedReceipt,
                         cace_keys: Mapping[str, str], approval_keys: Mapping[str, str],
                         suite_sha256: str, verifier=None) -> dict[str, Any]:
        if not verify_signed_receipt(cace_receipt, cace_keys, expected_issuer="cace",
            expected_claims={"candidate_id": candidate_id, "candidate_digest": artifact_sha256,
                             "benchmark_manifest_sha256": suite_sha256, "status": "pass",
                             "authority": "verification-only"}, verifier=verifier):
            raise PermissionError("CACE verification receipt does not authorize this artifact")
        if not verify_signed_receipt(approval_receipt, approval_keys, expected_issuer="merlin-approver",
            expected_claims={"candidate_id": candidate_id, "candidate_digest": artifact_sha256,
                             "action": "promote", "target": "qualified"}, verifier=verifier):
            raise PermissionError("explicit promotion approval receipt is missing or invalid")
        if not self.verify_chain()["valid"]:
            raise RuntimeError("ledger integrity check failed")
        return self.append("candidate.promoted", candidate_id, {
            "candidate_id": candidate_id, "artifact_sha256": artifact_sha256,
            "suite_sha256": suite_sha256, "cace_receipt_digest": cace_receipt.receipt_digest,
            "approval_receipt_digest": approval_receipt.receipt_digest,
            "promotion_authority": "explicit-signed-approval",
        })

    def verify_chain(self) -> dict[str, Any]:
        previous = "0" * 64
        count = 0
        with self._connect() as db:
            rows = db.execute("SELECT * FROM rsi_events ORDER BY seq").fetchall()
        for row in rows:
            payload_hash = sha256_hex(row["payload_json"].encode("utf-8"))
            material = {"event_type": row["event_type"], "entity_id": row["entity_id"],
                        "payload_sha256": payload_hash, "previous_hash": previous,
                        "created_at": row["created_at"]}
            calculated = sha256_hex(canonical_json(material))
            if row["payload_sha256"] != payload_hash or row["previous_hash"] != previous or row["event_hash"] != calculated:
                return {"valid": False, "checked": count, "failed_seq": row["seq"]}
            previous = calculated
            count += 1
        return {"valid": True, "checked": count, "head": previous}


def ingest_hermes_failure(ledger: AppendOnlyLedger, record: Mapping[str, Any],
                          receipt: SignedReceipt, trusted_keys: Mapping[str, str],
                          *, verifier=None) -> dict[str, Any]:
    """Turn an authenticated Hermes failure into an RSI induction seed."""
    required = ("event_id", "failure_class", "summary", "source_repo", "source_commit", "artifact_sha256")
    if any(not record.get(k) for k in required):
        raise ValueError("Hermes failure record is incomplete")
    claims = {"subject": "hermes-failure:" + str(record["event_id"]),
              "source_repo": record["source_repo"], "source_commit": record["source_commit"],
              "artifact_sha256": record["artifact_sha256"], "failure_class": record["failure_class"]}
    if not verify_signed_receipt(receipt, trusted_keys, expected_issuer="hermes",
                                 expected_claims=claims, verifier=verifier):
        raise PermissionError("Hermes failure lacks an authenticated source receipt")
    seed_id = "rsi-induction:" + str(record["event_id"])
    return ledger.append("rsi.induction_seeded", seed_id, {
        "hermes_event_id": record["event_id"], "failure_class": record["failure_class"],
        "summary": record["summary"], "source_repo": record["source_repo"],
        "source_commit": record["source_commit"], "artifact_sha256": record["artifact_sha256"],
        "source_receipt_digest": receipt.receipt_digest,
        "induction": {"generalize_failure": True, "generate_counterexample": True,
                      "propose_regression_test": True, "promotion_authority": False},
    })


class ResearchMetadataCache:
    """Crossref/arXiv metadata client with persistent cache and per-host throttling."""

    def __init__(self, database: str | Path, *, crossref_interval: float = 1.0,
                 arxiv_interval: float = 3.0, user_agent: str = "MerlinResearch/1.0 (mailto:research@example.invalid)"):
        self.database = str(database)
        self.intervals = {"api.crossref.org": max(1.0, crossref_interval),
                          "export.arxiv.org": max(3.0, arxiv_interval)}
        self.user_agent = user_agent
        self._last_request: dict[str, float] = {}
        with sqlite3.connect(self.database) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS research_metadata_cache (
                provider TEXT NOT NULL, identifier TEXT NOT NULL, response_json TEXT NOT NULL,
                response_sha256 TEXT NOT NULL, retrieved_at TEXT NOT NULL,
                PRIMARY KEY(provider,identifier))""")

    def _get(self, provider: str, identifier: str, url: str) -> dict[str, Any]:
        with sqlite3.connect(self.database) as db:
            row = db.execute("SELECT response_json,response_sha256 FROM research_metadata_cache WHERE provider=? AND identifier=?",
                             (provider,identifier)).fetchone()
        if row:
            body = row[0].encode("utf-8")
            if sha256_hex(body) != row[1]:
                raise RuntimeError("metadata cache integrity failure")
            return json.loads(row[0])
        host = urllib.parse.urlparse(url).hostname or ""
        interval = self.intervals[host]
        delay = interval - (time.monotonic() - self._last_request.get(host, 0.0))
        if delay > 0:
            time.sleep(delay)
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent, "Accept": "application/json, application/atom+xml"})
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read(2_000_000)
        self._last_request[host] = time.monotonic()
        if provider == "crossref":
            parsed = json.loads(raw.decode("utf-8"))
        else:
            root = ET.fromstring(raw)
            ns = {"a": "http://www.w3.org/2005/Atom"}
            entries = []
            for entry in root.findall("a:entry", ns):
                entries.append({
                    "id": (entry.findtext("a:id", default="", namespaces=ns)),
                    "title": " ".join((entry.findtext("a:title", default="", namespaces=ns)).split()),
                    "summary": " ".join((entry.findtext("a:summary", default="", namespaces=ns)).split()),
                    "published": entry.findtext("a:published", default="", namespaces=ns),
                    "authors": [a.findtext("a:name", default="", namespaces=ns) for a in entry.findall("a:author", ns)],
                })
            parsed = {"feed": entries}
        encoded = canonical_json(parsed).decode("utf-8")
        digest = sha256_hex(encoded.encode("utf-8"))
        with sqlite3.connect(self.database) as db:
            db.execute("INSERT OR REPLACE INTO research_metadata_cache VALUES (?,?,?,?,?)",
                       (provider,identifier,encoded,digest,datetime.now(timezone.utc).isoformat()))
        return parsed

    def crossref_doi(self, doi: str) -> dict[str, Any]:
        normalized = doi.strip().removeprefix("https://doi.org/").removeprefix("http://doi.org/")
        if not normalized or len(normalized) > 512:
            raise ValueError("invalid DOI")
        url = "https://api.crossref.org/works/" + urllib.parse.quote(normalized, safe="/")
        return self._get("crossref", normalized, url)

    def arxiv_id(self, arxiv_id: str) -> dict[str, Any]:
        normalized = arxiv_id.strip().removeprefix("https://arxiv.org/abs/")
        if not normalized or len(normalized) > 128:
            raise ValueError("invalid arXiv identifier")
        url = "https://export.arxiv.org/api/query?id_list=" + urllib.parse.quote(normalized, safe=".")
        return self._get("arxiv", normalized, url)


def paired_adapter_gain(baseline: list[float], candidate: list[float],
                        *, minimum_cases: int = 20, minimum_gain: float = 0.01) -> dict[str, Any]:
    """Conservative paired lower-bound gate; higher scores are better."""
    if len(baseline) != len(candidate) or len(baseline) < minimum_cases:
        return {"eligible": False, "reason": "insufficient_paired_cases"}
    deltas = [float(b) - float(a) for a,b in zip(baseline,candidate)]
    if any(not math.isfinite(x) for x in deltas):
        return {"eligible": False, "reason": "non_finite_measurement"}
    mean = statistics.mean(deltas)
    se = statistics.stdev(deltas) / math.sqrt(len(deltas)) if len(deltas) > 1 else math.inf
    lower = mean - 1.96 * se
    return {"eligible": lower >= minimum_gain, "mean_gain": mean,
            "lower_95_bound": lower, "cases": len(deltas),
            "reason": "measured_gain" if lower >= minimum_gain else "no_reliable_gain"}


def optional_adapter_status(package: str, baseline: list[float] | None = None,
                            candidate: list[float] | None = None) -> dict[str, Any]:
    """GEPA/Inspect stay off until installed and paired held-out results justify use."""
    import importlib.util
    installed = importlib.util.find_spec(package) is not None
    result = {"adapter": package, "installed": installed, "enabled": False,
              "reason": "not_installed" if not installed else "awaiting_paired_heldout_evidence"}
    if installed and baseline is not None and candidate is not None:
        gate = paired_adapter_gain(baseline, candidate)
        result.update(gate)
        result["enabled"] = bool(gate["eligible"])
    return result
