"""Regression contract for Android's locked-down bundled inference configuration."""
import ast
from pathlib import Path

def test_policy():
    text=Path(__file__).with_name("merlin_android.py").read_text()
    root=ast.parse(text)
    assert root
    assert 'engine.DEFAULTS["model_url"]' in text
    assert 'engine.DEFAULTS["model_timeout_seconds"] = 120' in text
    assert 'Only the bundled on-device AI server is permitted' in text
    assert 'MERLIN_MODEL_URL' in text

if __name__ == "__main__":
    test_policy()
    print("PASS: Android bundled model policy source contract")
