from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "python" / "merlin" / "hermes_stage_handlers.py").read_text(encoding="utf-8")
guide = (ROOT / "docs" / "MERLIN_AVREA_HERMES_ROUTING.md").read_text(encoding="utf-8")

assert "artifact_verifier: Callable[..., Mapping[str, Any]] | None" in source
assert '"verification_status": "blocked_missing_credentials"' in source
assert '"reason_code": "cace_verifier_not_configured"' in source
assert "artifact_verifier is None" in source
assert "CACE receipt" in source
assert "Never create placeholder secrets" in guide
assert "artifact_verifier=None" in guide
assert "blocked_missing_credentials" in guide
print("CACE optional-verifier fail-closed contract: PASS")
