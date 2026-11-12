from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas/merlin/continuum-structure.v1.schema.json"
SAMPLE_PATH = ROOT / "docs/research/paired-state-continuum-triangle.v1.json"


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_versioned_schema_and_sample_have_matching_top_level_contract() -> None:
    schema = _read(SCHEMA_PATH)
    sample = _read(SAMPLE_PATH)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    required = set(schema["required"])
    assert required == set(schema["properties"])
    assert required == set(sample)
    assert sample["schema_version"] == 1
    assert sample["version"] == "1.0.0"


def test_triangle_state_spaces_cells_and_edge_traces_are_consistent() -> None:
    sample = _read(SAMPLE_PATH)
    vertices = {item["id"]: item for item in sample["vertices"]}
    cells = {item["id"]: item for item in sample["cells"]}
    spaces = {item["id"]: item for item in sample["state_spaces"]}
    fields = {item["id"]: item for item in sample["edge_fields"]}
    assert len(vertices) == len(sample["vertices"]) == 3
    assert len(cells) == len(sample["cells"]) == 4
    assert len(fields) == len(sample["edge_fields"]) == 3
    assert len(spaces) == len(sample["state_spaces"]) == 1

    for cell in cells.values():
        assert cell["dimension"] <= sample["geometry"]["dimension"]
        assert cell["orientation"] in (-1, 1)
        assert all(vertex_id in vertices for vertex_id in cell["vertex_ids"])
        assert cell["state_space_id"] in spaces

    for field in fields.values():
        cell = cells[field["cell_id"]]
        space = spaces[field["state_space_id"]]
        assert cell["dimension"] == 1
        assert cell["state_space_id"] == field["state_space_id"]
        samples = field["samples"]
        parameters = [point["parameter"] for point in samples]
        assert parameters[0] == 0 and parameters[-1] == 1
        assert parameters == sorted(set(parameters))
        for point in samples:
            assert len(point["value"]) == space["dimension"]
        start_vertex, end_vertex = (vertices[key] for key in cell["vertex_ids"])
        assert samples[0]["value"] == start_vertex["state"]
        assert samples[-1]["value"] == end_vertex["state"]
        for point in samples:
            t = point["parameter"]
            expected = [
                start + (end - start) * t
                for start, end in zip(start_vertex["state"], end_vertex["state"])
            ]
            assert all(abs(actual - wanted) <= 1e-9
                       for actual, wanted in zip(point["value"], expected))

    # Explicitly check the three shared-vertex equalities in the declared orientation.
    assert fields["F_AB"]["samples"][-1]["value"] == fields["F_BC"]["samples"][0]["value"]
    assert fields["F_BC"]["samples"][-1]["value"] == fields["F_CA"]["samples"][0]["value"]
    assert fields["F_CA"]["samples"][-1]["value"] == fields["F_AB"]["samples"][0]["value"]


def test_transformations_invariants_and_evidence_keep_epistemic_boundaries() -> None:
    sample = _read(SAMPLE_PATH)
    spaces = {item["id"]: item for item in sample["state_spaces"]}
    for transform in sample["transformations"]:
        source = spaces[transform["source_state_space_id"]]
        target = spaces[transform["target_state_space_id"]]
        matrix = transform["matrix"]
        assert len(matrix) == target["dimension"]
        assert all(len(row) == source["dimension"] for row in matrix)

    assert any(
        item["id"] == "boundary-of-boundary-zero" and item["status"] == "finite_tested"
        for item in sample["invariants"]
    )
    assert sample["epistemic"] == {
        "claim_status": "candidate",
        "finite_test_status": "passed",
        "formal_proof_status": "not_formalized",
    }
    provenance = sample["provenance"]
    assert re.fullmatch(r"[0-9a-f]{40}", provenance["source_commit"])
    assert provenance["source_files"]
    assert all(re.fullmatch(r"[0-9a-f]{40}", item["git_blob_sha1"])
               for item in provenance["source_files"])
    assert sample["evidence"]
    assert all(item["proof_implication"] == "none" for item in sample["evidence"])
