import base64
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from merlin.rsi_pipeline import (
    AppendOnlyLedger, SignedReceipt, canonical_json, cace_rsi_bundle_sha256,
    ingest_hermes_failure, optional_adapter_status, paired_adapter_gain,
    paired_adapter_gate, sha256_hex,
)


def receipt(issuer, claims, key_id="test-key"):
    return SignedReceipt(
        1, issuer, key_id, datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        claims, base64.b64encode(b"ok").decode("ascii")
    )


def verifier(payload, signature, pem):
    return signature == b"ok" and pem == "test-public-key"


def cace_attestation(candidate_id, bundle_sha, bindings, key_id=None):
    key_id = key_id or ("ed25519:" + "d" * 64)
    statement = {
        "schema": "cace-attestation-statement-v1",
        "signature_algorithm": "ed25519",
        "proof_effect": "none",
        "verifier_id": "cace",
        "verifier_key_id": key_id,
        "claim_id": candidate_id,
        "bundle_sha256": bundle_sha,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": "independent-reproduction",
        "bindings": dict(bindings),
    }
    signing_bytes = b"CACE:SIGNED-ATTESTATION:v1\0" + canonical_json(statement)
    return {
        "schema": "cace-signed-attestation-v1",
        "signature_algorithm": "ed25519",
        "proof_effect": "none",
        "statement_sha256": sha256_hex(signing_bytes),
        "statement": statement,
        "public_key_pem": "test-public-key",
        "signature_b64": base64.b64encode(b"x" * 64).decode("ascii"),
    }


def cace_verifier(payload, signature, public_pem):
    return signature == b"x" * 64 and public_pem == "test-public-key", "ed25519:" + "d" * 64


class RSIPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "research_episodes.sqlite3"
        self.ledger = AppendOnlyLedger(self.db)
        self.keys = {"test-key": "test-public-key"}
        self.cace_keys = {"ed25519:" + "d" * 64: "cace"}
        self.artifact = "a" * 64
        self.suite = "b" * 64
        self.episode = "rsi-induction:hermes-17"

    def _source_receipt(self, candidate):
        return receipt("merlin-source", {
            "candidate_id": candidate, "artifact_sha256": self.artifact,
            "source_repo": "Mannyspiro/expert-robot", "source_commit": "c" * 40,
        })

    def _evaluation_receipt(self, candidate, metrics, passed=True):
        metrics_sha = sha256_hex(canonical_json(metrics))
        return receipt("merlin-evaluator", {
            "candidate_id": candidate, "candidate_digest": self.artifact,
            "benchmark_manifest_sha256": self.suite,
            "metrics_sha256": metrics_sha, "status": "pass" if passed else "fail",
        })

    def _candidate_and_eval(self, candidate="candidate-1"):
        self.ledger.record_candidate(
            candidate_id=candidate, parent_candidate_id=None,
            source_receipt=self._source_receipt(candidate),
            artifact_sha256=self.artifact, generator="hermes-rsi",
            mutation={"failure_class": "lean-timeout"},
            trusted_keys=self.keys, episode_id=self.episode, verifier=verifier)
        metrics = {"score": 0.9}
        evaluation = self._evaluation_receipt(candidate, metrics)
        self.ledger.record_evaluation(
            candidate_id=candidate, artifact_sha256=self.artifact,
            suite_sha256=self.suite, metrics=metrics, passed=True,
            evaluator_receipt=evaluation, trusted_keys=self.keys,
            episode_id=self.episode, verifier=verifier)
        bindings = {
            "candidate_id": candidate, "candidate_digest": self.artifact,
            "benchmark_manifest_sha256": self.suite,
            "evaluator_receipt_sha256": evaluation.receipt_digest,
            "source_repo": "Mannyspiro/expert-robot", "source_commit": "c" * 40,
            "authority": "verification-only",
        }
        bundle = cace_rsi_bundle_sha256(
            candidate_id=candidate, candidate_digest=self.artifact,
            benchmark_manifest_sha256=self.suite,
            evaluator_receipt_sha256=evaluation.receipt_digest,
            source_repo="Mannyspiro/expert-robot", source_commit="c" * 40)
        return evaluation, bindings, bundle

    def test_hermes_failure_requires_authenticated_source_and_is_idempotent(self):
        record = {"event_id": "hermes-17", "failure_class": "lean-timeout",
                  "summary": "Proof search exceeded its budget",
                  "source_repo": "Mannyspiro/expert-robot",
                  "source_commit": "c" * 40, "artifact_sha256": self.artifact}
        claims = {"subject": "hermes-failure:hermes-17",
                  "source_repo": record["source_repo"], "source_commit": record["source_commit"],
                  "artifact_sha256": self.artifact, "failure_class": "lean-timeout"}
        bad = receipt("hermes", {**claims, "source_commit": "d" * 40})
        with self.assertRaises(PermissionError):
            ingest_hermes_failure(self.ledger, record, bad, self.keys, verifier=verifier)
        good = receipt("hermes", claims)
        first = ingest_hermes_failure(self.ledger, record, good, self.keys, verifier=verifier)
        second = ingest_hermes_failure(self.ledger, record, good, self.keys, verifier=verifier)
        self.assertEqual(first["seq"], 0)
        self.assertTrue(second["idempotent_replay"])
        self.assertTrue(self.ledger.verify_chain(self.episode.replace("rsi-induction:", "rsi-induction:"))["valid"])

    def test_candidate_requires_signed_source_and_existing_parent(self):
        child = "candidate-child"
        with self.assertRaises(ValueError):
            self.ledger.record_candidate(
                candidate_id=child, parent_candidate_id="missing-parent",
                source_receipt=self._source_receipt(child), artifact_sha256=self.artifact,
                generator="hermes-rsi", mutation={}, trusted_keys=self.keys,
                episode_id=self.episode, verifier=verifier)
        root = "candidate-root"
        self.ledger.record_candidate(
            candidate_id=root, parent_candidate_id=None,
            source_receipt=self._source_receipt(root), artifact_sha256=self.artifact,
            generator="hermes-rsi", mutation={}, trusted_keys=self.keys,
            episode_id=self.episode, verifier=verifier)
        self.ledger.record_candidate(
            candidate_id=child, parent_candidate_id=root,
            source_receipt=self._source_receipt(child), artifact_sha256=self.artifact,
            generator="hermes-rsi", mutation={}, trusted_keys=self.keys,
            episode_id=self.episode, verifier=verifier)
        self.assertTrue(self.ledger.verify_chain(self.episode)["valid"])

    def test_evaluation_requires_signed_bound_receipt(self):
        candidate = "candidate-eval"
        self.ledger.record_candidate(
            candidate_id=candidate, parent_candidate_id=None,
            source_receipt=self._source_receipt(candidate), artifact_sha256=self.artifact,
            generator="hermes-rsi", mutation={}, trusted_keys=self.keys,
            episode_id=self.episode, verifier=verifier)
        metrics = {"score": 0.9}
        bad = receipt("merlin-evaluator", {
            "candidate_id": candidate, "candidate_digest": "f" * 64,
            "benchmark_manifest_sha256": self.suite,
            "metrics_sha256": sha256_hex(canonical_json(metrics)), "status": "pass"})
        with self.assertRaises(PermissionError):
            self.ledger.record_evaluation(
                candidate_id=candidate, artifact_sha256=self.artifact,
                suite_sha256=self.suite, metrics=metrics, passed=True,
                evaluator_receipt=bad, trusted_keys=self.keys,
                episode_id=self.episode, verifier=verifier)

    def test_cace_attestation_and_separate_approval_required_for_promotion(self):
        candidate = "candidate-cace"
        evaluation, bindings, bundle = self._candidate_and_eval(candidate)
        attestation = cace_attestation(candidate, bundle, bindings)
        cace_event = self.ledger.record_cace_verification(
            candidate_id=candidate, attestation=attestation,
            approved_keys=self.cace_keys, artifact_sha256=self.artifact,
            suite_sha256=self.suite, episode_id=self.episode,
            cace_verifier=cace_verifier)
        self.assertEqual(cace_event["seq"], 2)
        digest = sha256_hex(canonical_json(attestation))
        approval = receipt("merlin-approver", {
            "candidate_id": candidate, "candidate_digest": self.artifact,
            "benchmark_manifest_sha256": self.suite,
            "cace_attestation_sha256": digest,
            "action": "promote", "target": "qualified"})
        promoted = self.ledger.record_promotion(
            candidate_id=candidate, artifact_sha256=self.artifact,
            suite_sha256=self.suite, attestation=attestation,
            cace_approved_keys=self.cace_keys, approval_receipt=approval,
            approval_keys=self.keys, episode_id=self.episode,
            cace_verifier=cace_verifier, approval_verifier=verifier)
        self.assertEqual(promoted["seq"], 3)
        self.assertTrue(self.ledger.verify_chain(self.episode)["valid"])

    def test_cace_embedded_key_is_not_trusted_without_allowlist(self):
        candidate = "candidate-untrusted"
        _, bindings, bundle = self._candidate_and_eval(candidate)
        attestation = cace_attestation(candidate, bundle, bindings)
        with self.assertRaises(PermissionError):
            self.ledger.record_cace_verification(
                candidate_id=candidate, attestation=attestation,
                approved_keys={}, artifact_sha256=self.artifact,
                suite_sha256=self.suite, episode_id=self.episode,
                cace_verifier=cace_verifier)

    def test_promotion_fails_without_prior_cace_event(self):
        candidate = "candidate-no-cace"
        _, bindings, bundle = self._candidate_and_eval(candidate)
        attestation = cace_attestation(candidate, bundle, bindings)
        approval = receipt("merlin-approver", {
            "candidate_id": candidate, "candidate_digest": self.artifact,
            "benchmark_manifest_sha256": self.suite,
            "cace_attestation_sha256": sha256_hex(canonical_json(attestation)),
            "action": "promote", "target": "qualified"})
        with self.assertRaises(PermissionError):
            self.ledger.record_promotion(
                candidate_id=candidate, artifact_sha256=self.artifact,
                suite_sha256=self.suite, attestation=attestation,
                cace_approved_keys=self.cace_keys, approval_receipt=approval,
                approval_keys=self.keys, episode_id=self.episode,
                cace_verifier=cace_verifier, approval_verifier=verifier)

    def test_python_adapter_uses_cpp_research_episode_ledger_schema(self):
        event = self.ledger.append("test.event", self.episode, {"value": 1})
        with sqlite3.connect(self.db) as db:
            row = db.execute(
                "SELECT episode_id,sequence,event_type,payload,payload_sha256,"
                "previous_event_hash,event_hash FROM research_episode_events").fetchone()
        self.assertEqual(row[0], self.episode)
        self.assertEqual(row[1], 0)
        payload_hash = sha256_hex(row[3].encode())
        material = (f"episode={row[0]}\nsequence={row[1]}\ntype={row[2]}\n"
                    f"payload_sha256={payload_hash}\nprevious_event_hash=\n")
        self.assertEqual(row[4], payload_hash)
        self.assertEqual(row[6], sha256_hex(material.encode()))
        self.assertEqual(event["event_hash"], row[6])

    def test_ledger_rejects_update_delete_and_detects_trigger_bypass_tampering(self):
        self.ledger.append("test.event", self.episode, {"value": 1})
        with sqlite3.connect(self.db) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE research_episode_events SET payload='tampered' WHERE episode_id=?",
                           (self.episode,))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM research_episode_events WHERE episode_id=?",
                           (self.episode,))
            db.execute("DROP TRIGGER research_episode_events_no_update")
            db.execute("UPDATE research_episode_events SET payload='tampered' WHERE episode_id=?",
                       (self.episode,))
        self.assertFalse(self.ledger.verify_chain(self.episode)["valid"])

    def test_fixed_holdout_covers_all_five_domains(self):
        manifest_path = Path(__file__).resolve().parents[1] / "config/benchmarks/merlin_rsi_multidomain_holdout_v1.json"
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["status"], "frozen")
        self.assertEqual(set(manifest["domains"]),
                         {"mathematics", "lean", "research", "coding", "engineering"})
        self.assertEqual(len(manifest["cases"]), 25)
        self.assertEqual(len({case["id"] for case in manifest["cases"]}), 25)
        self.assertTrue(all(case["domain"] in manifest["domains"] for case in manifest["cases"]))

    def test_crossref_cache_persists_and_avoids_duplicate_request(self):
        body = json.dumps({"status": "ok", "message": {"title": ["Test paper"]}}).encode()
        with patch("urllib.request.urlopen", return_value=io.BytesIO(body)) as open_url:
            cache = __import__("merlin.rsi_pipeline", fromlist=["ResearchMetadataCache"]).ResearchMetadataCache(
                self.db, cache_ttl_seconds=3600)
            first = cache.crossref_doi("10.1234/example")
            second = cache.crossref_doi("https://doi.org/10.1234/example")
        self.assertEqual(first, second)
        self.assertEqual(open_url.call_count, 1)
        self.assertEqual(first["message"]["title"][0], "Test paper")

    def test_arxiv_metadata_is_parsed_and_cached(self):
        xml = b'''<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry><id>http://arxiv.org/abs/2601.00001v1</id>
          <title> A useful theorem </title><summary> Abstract text </summary>
          <published>2026-01-01T00:00:00Z</published>
          <author><name>Author One</name></author></entry>
        </feed>'''
        with patch("urllib.request.urlopen", return_value=io.BytesIO(xml)) as open_url:
            cache = __import__("merlin.rsi_pipeline", fromlist=["ResearchMetadataCache"]).ResearchMetadataCache(
                self.db, cache_ttl_seconds=3600)
            first = cache.arxiv_id("2601.00001")
            second = cache.arxiv_id("2601.00001")
        self.assertEqual(first, second)
        self.assertEqual(open_url.call_count, 1)
        self.assertEqual(first["feed"][0]["title"], "A useful theorem")
        self.assertEqual(first["feed"][0]["authors"], ["Author One"])

    def test_rate_limit_is_shared_across_cache_instances(self):
        from merlin.rsi_pipeline import ResearchMetadataCache
        a = ResearchMetadataCache(self.db)
        b = ResearchMetadataCache(self.db)
        with patch("merlin.rsi_pipeline.time.time", return_value=1000.0), \
             patch("merlin.rsi_pipeline.time.sleep") as sleep:
            a._reserve_rate_slot("api.crossref.org")
            b._reserve_rate_slot("api.crossref.org")
        sleep.assert_called_once_with(1.0)

    def test_adapter_gate_requires_paired_improvement_without_domain_regression(self):
        domains = ["mathematics", "lean", "research", "coding", "engineering"]
        baseline = {d: [0.5] * 5 for d in domains}
        improved = {d: [0.6] * 5 for d in domains}
        self.assertTrue(paired_adapter_gate(baseline, improved)["eligible"])
        regressed = dict(improved)
        regressed["engineering"] = [0.4] * 5
        self.assertFalse(paired_adapter_gate(baseline, regressed)["eligible"])
        self.assertFalse(paired_adapter_gain([0.5] * 5, [0.8] * 5)["eligible"])
        self.assertFalse(optional_adapter_status(
            "merlin_nonexistent_optional_adapter")["enabled"])


if __name__ == "__main__":
    unittest.main()
