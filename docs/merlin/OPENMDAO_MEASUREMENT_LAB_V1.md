# Optional OpenMDAO scalar-measurement lab

Implemented locally against real OpenMDAO **3.45.2**, release commit
[`64175aa55fb541355b2fb279a6bcfde01e17a878`](https://github.com/OpenMDAO/OpenMDAO/commit/64175aa55fb541355b2fb279a6bcfde01e17a878).
NASA lists OpenMDAO as open-source software in its
[software catalog](https://software.nasa.gov/software/LEW-19994-1).
The pinned upstream [LICENSE.txt](https://github.com/OpenMDAO/OpenMDAO/blob/64175aa55fb541355b2fb279a6bcfde01e17a878/LICENSE.txt)
and [package metadata](https://github.com/OpenMDAO/OpenMDAO/blob/64175aa55fb541355b2fb279a6bcfde01e17a878/pyproject.toml)
declare Apache-2.0. No upstream repository or library source is vendored.

`merlin.openmdao_measurement.compare_with_openmdao(observation, predictions)`
normalizes bounded scalar measurements and predictions, then calls the existing
`scientific_loop.compare_observation` once. `scientific_loop.py` is unchanged.
Normal application startup imports no OpenMDAO dependency. Explicit use without
the exact optional package/source pin raises `OpenMDAOUnavailable`;
`backend_status()` reports `blocked_optional_dependency`. There is no fallback
converter, automatic install, optimizer, network request or promotion action.

The unit allowlist covers length, time, mass, force, pressure, power, speed and
absolute temperature. Unknown/custom expressions never reach OpenMDAO's unit
parser. Incompatible dimensions retain `incomparable_unit`. The adapter allows
at most32 measurements and64 predictions and rejects nonfinite/overflow values.

For OpenMDAO's affine conversion, the center becomes `(value + offset) * factor`.
An uncertainty/tolerance half-width becomes `abs(factor) * width`; adding an
offset to uncertainty would be physically wrong. Absolute temperatures normalize
to Kelvin, and both observed and predicted intervals must remain nonnegative.
Delta-temperature quantities and correlated/probabilistic uncertainty are outside
this profile. Half-widths do not assert calibrated confidence levels.

The synthetic demo compares **68 ±1.8°F** with **20 ±1.1°C**. Existing comparison
returns `incomparable_unit`; normalization yields the observed interval
**[292.15,294.15]K**, consistent with the prediction. This is a useful unit-label
repair, not evidence of model accuracy, a real thermometer calibration, or a
general performance gain. Independent fixed physical oracles also cover100cm=1m,
0°C=273.15K, incompatible length/time, overlap/refutation and invalid intervals.

Reproduce with Python3.12 in an isolated environment:

```bash
python3.12 -m venv .venv-openmdao
.venv-openmdao/bin/python -m pip install -r requirements-merlin-openmdao.txt
PYTHONPATH=python .venv-openmdao/bin/python -m unittest discover -s tests -p test_openmdao_measurement.py -v
PYTHONPATH=python .venv-openmdao/bin/python -c 'import json; from merlin.openmdao_measurement import run_synthetic_demo; print(json.dumps(run_synthetic_demo(), indent=2))'
```

The lock records the actual dependency versions tested, including networkx3.7
which requires Python3.12. OpenMDAO alone supports Python>=3.10. The current
private OCI service's Python3.9 cannot run this profile; nothing was installed,
restarted or deployed there. Another dependency/runtime profile needs separate
acceptance, rather than silently relaxing the pin.

Installed `openmdao/utils/units.py` and `unit_library.ini` were byte-checked against
the exact upstream Git blobs; their SHA-256 values are enforced by this adapter.
The versioned [evidence receipt](OPENMDAO_MEASUREMENT_EVIDENCE_20261118.json)
records measured tests, dependency/runtime versions, source hashes and demo output.
The examples are public synthetic fixtures, known in advance and non-blind.
No NASA approval, FIPS validation, CACE qualification, physical qualification,
learning efficacy or promotion authority is claimed.
