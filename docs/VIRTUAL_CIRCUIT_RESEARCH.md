# Bounded virtual circuit research

`dot_ai_os.simulation_research` compares a baseline and up to four candidate
resistor networks using the existing Merlin `EngineeringProject`, `Part`, `Pin`
and `Net` types. The same typed project supplies the canonical wiring JSON,
SPICE operating-point deck and OpenSCAD box-assembly preview. Geometry never
supplies missing electrical values.

The offline solver handles 2–24 two-terminal parts, 2–14 nets, one ideal
ground-referenced source at 0–12 V, and explicitly specified 100–1,000,000 ohm
resistors. Inputs use bounded decimal SI strings. Exact rational nodal analysis
reports node voltages, declared-pin-order branch currents, resistor power, KCL
and power-balance residuals. Floating circuits and unsupported components fail
closed. It does not invoke ngspice, FreeCAD, hardware, a model, a network or a VM.

```python
from dot_ai_os.simulation_research import (
    CircuitCandidate, CircuitObjective, compare_virtual_circuits, divider_project,
)

def divider(name, resistance):
    return CircuitCandidate(name, {
        "V1": {"kind": "V", "value": "5"},
        "R1": {"kind": "R", "value": resistance},
        "R2": {"kind": "R", "value": resistance},
    })

report = compare_virtual_circuits(
    divider_project(), divider("baseline", "1000"),
    (divider("candidate", "9000"),),
    CircuitObjective("GND", "OUT", "2.5", "0.01", "0.1"),
    source_commit=exact_source_commit,
)
```

Candidates retain topology, component kinds and source values. Ranking prefers
meeting the declared voltage, total-power and supplied pin-rating constraints,
then smaller voltage error and lower modeled dissipation. A winner is a proposal
for further review. Failed/null constraint outcomes remain in the result.
Optional `registry=canonical_registry, project_id=existing_project_id` stores a
replayable, content-addressed report through `MerlinRegistry`; it creates no
claims, signatures or qualification receipts.

`virtual_circuit_demo(arguments)` is the fixed dict-only private-host handler.
It accepts `{}` or `{"operation": "demo"}` and rejects all other input fields
and operations. It runs the fixed 1k/1k versus 9k/9k comparison above, reads no
private context or registry, and bounds its complete report to 48,000 bytes.
The report includes canonical CAD/wiring/SPICE exports and explicit simulation
limits. A host may statically register it; callers cannot select code, imports,
files, source pins, processes or network endpoints.

Dependencies inspected at Expert Robot commit
`703b21e3639c239484e851bebdb1a60c755d4924`:

- `python/merlin/engineering_ir.py`: canonical types, validation and exports.
- `python/merlin/project_registry.py` and `python/merlin/artifact_ref.py`: optional artifact persistence.
- `python/dot_ai_os/bridge.py`: canonical JSON encoding and SHA-256 helper.

The simulation core uses Python standard-library features compatible with
Python 3.9; local tests ran under Python 3.12. A host Python 3.9 run remains
necessary before claiming host compatibility. No dependency installation is
required. HTTP/MCP integration has its own runtime requirements.

Validation command from the workspace:

```bash
PYTHONPATH=dot-ai-os/python:runtime-reference/python python -m unittest discover -s dot-ai-os/tests -p test_simulation_research.py -v
```

Results describe an ideal constant-resistance DC model. They omit tolerances,
temperature drift, dynamics, parasitics, source impedance and unmodeled loads.
Zero arithmetic residuals do not establish real-world accuracy, electrical
safety, formal proof or independent CACE verification. CAD output is a box
preview, not fabrication-ready design. Nothing is automatically adopted,
promoted, deployed, built or energized.
