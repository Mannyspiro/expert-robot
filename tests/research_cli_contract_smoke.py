#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
src=(ROOT/"cpp/src/research_cli_main.cpp").read_text()
cmake=(ROOT/"CMakeLists.txt").read_text()
runtime=(ROOT/"cpp/src/runtime.cpp").read_text()

for needle in (
    "LlamaServerProcess",
    "LlamaCliBackend",
    "LeanSubprocessRunner",
    "MathResearchService",
    "ModelFormalizationProposer",
    "formalization_proposal.schema.json",
    "lemma_decomposition.schema.json",
    "--model",
    "--claim",
):
    assert needle in src, needle

assert "add_executable(expert_robot_research" in cmake
assert "model backend not connected yet" not in runtime
assert "use expert_robot_research" in runtime
print("research CLI contract smoke: PASS")
