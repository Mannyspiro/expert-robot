"""Point-in-time public-data and prediction-market research primitives.

This module performs no network access and places no orders. Callers supply
lawfully obtained source bytes and market quotes. Snapshot bytes are
content-addressed; observations are append-only and filtered by availability
time to prevent look-ahead leakage in historical research.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit


def _timestamp(value: str, field: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _required(value: str, field: str, limit: int = 500) -> str:
    result = " ".join(str(value).split()).strip()
    if not result or len(result) > limit:
        raise ValueError(f"{field} is required and must be at most {limit} characters")
    return result


@dataclass(frozen=True)
class PublicSnapshot:
    source_id: str
    source_url: str
    retrieved_at: str
    published_at: str
    sha256: str
    byte_length: int
    terms_reviewed: bool


@dataclass(frozen=True)
class PointInTimeObservation:
    observation_id: str
    source_id: str
    snapshot_sha256: str
    entity_id: str
    metric: str
    period_start: str
    period_end: str
    available_at: str
    value: str
    unit: str
    currency: str
    vintage: str


class PublicResearchStore:
    """SQLite metadata plus immutable content-addressed raw source snapshots."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.blobs = self.root / "blobs" / "sha256"
        self.blobs.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "public_research.sqlite3"
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS snapshots(
                    sha256 TEXT PRIMARY KEY, source_id TEXT NOT NULL,
                    source_url TEXT NOT NULL, retrieved_at TEXT NOT NULL,
                    published_at TEXT NOT NULL, byte_length INTEGER NOT NULL,
                    terms_reviewed INTEGER NOT NULL CHECK(terms_reviewed=1)
                );
                CREATE INDEX IF NOT EXISTS idx_snapshots_source
                    ON snapshots(source_id, retrieved_at);
                CREATE TABLE IF NOT EXISTS observations(
                    observation_id TEXT PRIMARY KEY, source_id TEXT NOT NULL,
                    snapshot_sha256 TEXT NOT NULL REFERENCES snapshots(sha256),
                    entity_id TEXT NOT NULL, metric TEXT NOT NULL,
                    period_start TEXT NOT NULL, period_end TEXT NOT NULL,
                    available_at TEXT NOT NULL, value TEXT NOT NULL,
                    unit TEXT NOT NULL, currency TEXT NOT NULL, vintage TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_observation_pit
                    ON observations(entity_id, metric, period_end, available_at);
            """)

    def _connect(self):
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def add_snapshot(self, *, source_id: str, source_url: str, content: bytes,
                     retrieved_at: str, published_at: str,
                     terms_reviewed: bool) -> PublicSnapshot:
        source_id = _required(source_id, "source_id", 120)
        url = _required(source_url, "source_url", 2000)
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("source_url must be a public HTTPS URL without embedded credentials")
        if not isinstance(content, bytes) or not content:
            raise ValueError("snapshot content must be non-empty bytes")
        if terms_reviewed is not True:
            raise ValueError("source terms must be reviewed before retaining a snapshot")
        retrieved = _timestamp(retrieved_at, "retrieved_at")
        published = _timestamp(published_at, "published_at")
        digest = hashlib.sha256(content).hexdigest()
        target = self.blobs / digest[:2] / digest[2:]
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise RuntimeError("content-addressed snapshot integrity mismatch")
        else:
            temp = target.with_suffix(".tmp")
            temp.write_bytes(content)
            temp.replace(target)
        with self._connect() as db:
            db.execute("INSERT OR IGNORE INTO snapshots VALUES(?,?,?,?,?,?,1)",
                       (digest, source_id, url, retrieved, published, len(content)))
            row = db.execute("SELECT source_id,source_url FROM snapshots WHERE sha256=?",
                             (digest,)).fetchone()
            if row["source_id"] != source_id or row["source_url"] != url:
                raise ValueError("identical bytes cannot be rebound to different source metadata")
        return PublicSnapshot(source_id, url, retrieved, published, digest, len(content), True)

    def add_observation(self, *, observation_id: str, source_id: str,
                        snapshot_sha256: str, entity_id: str, metric: str,
                        period_start: str, period_end: str, available_at: str,
                        value: str | int | float, unit: str, currency: str = "",
                        vintage: str = "") -> PointInTimeObservation:
        fields = {
            "observation_id": _required(observation_id, "observation_id", 160),
            "source_id": _required(source_id, "source_id", 120),
            "entity_id": _required(entity_id, "entity_id", 200),
            "metric": _required(metric, "metric", 200),
            "unit": _required(unit, "unit", 80),
            "currency": str(currency).strip().upper(),
            "vintage": str(vintage).strip(),
        }
        if not re.fullmatch(r"[0-9a-f]{64}", snapshot_sha256):
            raise ValueError("snapshot_sha256 must be a lowercase SHA-256 digest")
        start = _timestamp(period_start, "period_start")
        end = _timestamp(period_end, "period_end")
        available = _timestamp(available_at, "available_at")
        if start > end:
            raise ValueError("period_start must not be after period_end")
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ValueError("value must be a scalar string or number")
        value_text = str(value).strip()
        if not value_text:
            raise ValueError("value is required")
        record = PointInTimeObservation(
            fields["observation_id"], fields["source_id"], snapshot_sha256,
            fields["entity_id"], fields["metric"], start, end, available,
            value_text, fields["unit"], fields["currency"], fields["vintage"],
        )
        with self._connect() as db:
            snapshot = db.execute("SELECT source_id FROM snapshots WHERE sha256=?",
                                  (snapshot_sha256,)).fetchone()
            if snapshot is None:
                raise ValueError("observation must reference an ingested raw snapshot")
            if snapshot["source_id"] != fields["source_id"]:
                raise ValueError("observation source_id must match its raw snapshot")
            db.execute("INSERT INTO observations VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                       tuple(asdict(record).values()))
        return record

    def query_as_of(self, *, entity_id: str, metric: str,
                    cutoff: str) -> list[PointInTimeObservation]:
        """Return latest available vintage per period; exclude future releases."""
        entity = _required(entity_id, "entity_id", 200)
        name = _required(metric, "metric", 200)
        at = _timestamp(cutoff, "cutoff")
        with self._connect() as db:
            rows = db.execute("""
                SELECT o.* FROM observations o
                JOIN (
                    SELECT period_start, period_end, MAX(available_at) AS latest_available
                    FROM observations
                    WHERE entity_id=? AND metric=? AND available_at<=?
                    GROUP BY period_start, period_end
                ) latest
                ON o.period_start=latest.period_start
                AND o.period_end=latest.period_end
                AND o.available_at=latest.latest_available
                WHERE o.entity_id=? AND o.metric=? AND o.available_at<=?
                ORDER BY o.period_end, o.available_at, o.observation_id
            """, (entity, name, at, entity, name, at)).fetchall()
        return [PointInTimeObservation(**dict(row)) for row in rows]

    def verify_snapshot(self, digest: str) -> bool:
        if not re.fullmatch(r"[0-9a-f]{64}", digest or ""):
            return False
        path = self.blobs / digest[:2] / digest[2:]
        return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest


@dataclass(frozen=True)
class KalshiQuote:
    ticker: str
    title: str
    yes_ask_cents: int
    no_ask_cents: int
    observed_at: str
    rules_url: str


def evaluate_binary_market(*, quote: KalshiQuote, estimated_yes_probability: float,
                           fee_per_contract_dollars: float = 0.0,
                           minimum_edge: float = 0.02) -> dict[str, Any]:
    """Compare independent probability with executable asks; never place orders."""
    if not 0.0 <= estimated_yes_probability <= 1.0:
        raise ValueError("estimated_yes_probability must be between zero and one")
    if (not isinstance(quote.yes_ask_cents, int) or isinstance(quote.yes_ask_cents, bool)
            or not isinstance(quote.no_ask_cents, int) or isinstance(quote.no_ask_cents, bool)
            or not 0 <= quote.yes_ask_cents <= 100 or not 0 <= quote.no_ask_cents <= 100):
        raise ValueError("ask prices must be integer cents between 0 and 100")
    if fee_per_contract_dollars < 0 or minimum_edge < 0:
        raise ValueError("fees and minimum_edge must be non-negative")
    observed = _timestamp(quote.observed_at, "observed_at")
    rules = _required(quote.rules_url, "rules_url", 2000)
    if urlsplit(rules).scheme != "https":
        raise ValueError("rules_url must use HTTPS")
    yes_edge = estimated_yes_probability - quote.yes_ask_cents / 100.0 - fee_per_contract_dollars
    no_edge = (1.0 - estimated_yes_probability) - quote.no_ask_cents / 100.0 - fee_per_contract_dollars
    candidates = []
    if yes_edge >= minimum_edge:
        candidates.append({"side": "YES", "estimated_net_edge_per_contract": round(yes_edge, 6)})
    if no_edge >= minimum_edge:
        candidates.append({"side": "NO", "estimated_net_edge_per_contract": round(no_edge, 6)})
    return {
        "schema": "merlin-kalshi-research/1",
        "ticker": _required(quote.ticker, "ticker", 120),
        "title": _required(quote.title, "title", 500),
        "observed_at": observed, "rules_url": rules,
        "estimated_yes_probability": estimated_yes_probability,
        "yes_ask_cents": quote.yes_ask_cents, "no_ask_cents": quote.no_ask_cents,
        "fee_per_contract_dollars": fee_per_contract_dollars,
        "yes_net_edge_per_contract": round(yes_edge, 6),
        "no_net_edge_per_contract": round(no_edge, 6),
        "research_candidates": candidates, "is_trade_instruction": False,
        "limitations": [
            "probability is an external model estimate, not a verified forecast",
            "ask quote may not represent sufficient available depth",
            "contract rules and settlement source require independent review",
            "fees must match the applicable fee schedule",
            "edge is not a guarantee of profit",
        ],
    }


BMC_RESEARCH_CURRICULUM = (
    "economics_and_indicators", "currencies_and_fx", "fixed_income_and_yield_curves",
    "equities_and_valuation", "commodities_and_supply_demand", "derivatives_and_options",
    "portfolio_management", "market_microstructure", "prediction_market_probability",
)

PUBLIC_SEARCH_TEMPLATES = {
    "macro_release": 'site:bls.gov OR site:bea.gov "{topic}" "{period}"',
    "central_bank": 'site:federalreserve.gov "{topic}" after:{after_date}',
    "issuer_filing": 'site:sec.gov/Archives/edgar/data/ "{issuer}" "{form_type}"',
    "energy_data": 'site:eia.gov "{topic}" filetype:pdf OR filetype:xlsx',
    "academic_replication": 'site:arxiv.org "{topic}" replication code dataset',
    "treasury_data": 'site:home.treasury.gov "{topic}" historical data',
}

__all__ = [
    "BMC_RESEARCH_CURRICULUM", "PUBLIC_SEARCH_TEMPLATES", "KalshiQuote",
    "PointInTimeObservation", "PublicResearchStore", "PublicSnapshot",
    "evaluate_binary_market",
]
