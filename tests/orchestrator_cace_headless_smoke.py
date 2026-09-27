#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

import orchestrator


class FakeConfig:
    @classmethod
    def load(cls, path):
        return {"path": str(path)}


class FakeClient:
    def __init__(self, config, *, timeout=30.0):
        self.config = config
        self.timeout = timeout

    def research_turn(self, prompt: str):
        assert "Role: math" in prompt
        assert "Task: prove a bounded lemma" in prompt
        assert "do not claim they executed" in prompt
        return {
            "schema_version": 1,
            "text": "I propose a typed CACE formal check.",
            "untrusted": True,
            "can_promote": False,
        }


def main() -> int:
    original_config = orchestrator.HeadlessConfig
    original_client = orchestrator.CACEHeadlessClient
    orchestrator.HeadlessConfig = FakeConfig
    orchestrator.CACEHeadlessClient = FakeClient
    try:
        admitted = {
            "id": "r1",
            "ok": True,
            "result": "runtime accepted task; model backend not connected yet",
            "error": "",
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = orchestrator.cace_reasoned_response(
                admitted,
                role="math",
                task="prove a bounded lemma",
                config_path=Path(tmp) / "config.json",
                timeout=2.0,
            )
        assert result["ok"] is True
        assert result["reasoning_backend"] == "cace-headless-local"
        assert result["runtime_admission"] == admitted
        assert result["assistant"]["untrusted"] is True
        assert result["assistant"]["can_promote"] is False
        assert result["authority_expanded"] is False

        rejected = {"id": "r2", "ok": False, "error": "denied"}
        assert orchestrator.cace_reasoned_response(
            rejected,
            role="math",
            task="ignored",
            config_path="unused.json",
        ) is rejected
    finally:
        orchestrator.HeadlessConfig = original_config
        orchestrator.CACEHeadlessClient = original_client

    print("Expert Robot CACE reasoning bridge smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
