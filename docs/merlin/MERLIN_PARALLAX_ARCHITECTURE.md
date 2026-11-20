# Parallax tensor architecture and Merlin replay

## Simulated package

Extend the prior Merlin tensor material screen with two optimistic transport cases and a throughput ceiling. The screen enumerates 32 combinations across four spreaders, two lane counts, two memory bandwidths and two arithmetic intensities. Treat the exotic case as an assumed very high through-plane conductivity, and zero bulk resistance as the mathematical endpoint. Hold contact and heatsink resistance fixed. This isolates the spreader and exposes the effect of the remaining thermal path. The copper and diamond conductivities are illustrative inputs from the prior screen. Diamond and numerical limits motivate sensitivity analysis without asserting a realizable exotic material.

At 64 lanes and 128 GB/s the thermal ceiling is 61.76 billion contraction primitives/s for copper, 62.74 for diamond and 63.13 in the zero-bulk-resistance limit. At 32 GB/s and 0.5 primitive/byte, all four spreaders are capped at 16 billion/s. Relative to copper, eliminating all spreader resistance gains at most about 2.2% in the tested thermally limited configurations. These figures assume 1 GHz, 0.8 nJ per primitive, a 12 W idle draw, a 45 K temperature rise allowance and a fixed interface/sink. They are upper bounds under those assumptions and do not imply hardware performance. Bench temperatures, device energy, bandwidth under load, hot spots and full Merlin inference were outside this model.

The architecture worth testing uses a conventional spreader baseline, local operand reuse, and a wider link only where measured traffic warrants it. QvGPU can remain a separate exact stabilizer accelerator workload. The screen supplies no case for routing ordinary tensor contraction through it.

## Bounded software RSI

Compare grouped (parent), padded and deduplicated packing on deterministic development workloads. Freeze the fastest layout before running two separate held-out seeds. The acceptance gate requires at least 10% speedup on each held-out seed and exact agreement on every output, including a directed narrowing-overflow case. Median times include one preparation amortized over eight replays. Timings cover local host execution.

| Held-out workload | Layout | Parent / candidate, seed 17701 | Parent / candidate, seed 17729 |
| --- | --- | ---: | ---: |
| Repeated | Deduplicated | 2.879 / 2.176 ms | 2.660 / 1.976 ms |
| Diverse | Padded | 2.932 / 2.286 ms | 2.957 / 2.218 ms |

Both layouts passed the local gate on their workload class. Merlin Studio already uses deduplication for the known repetitive replay preset. Padded is qualified locally for the synthetic diverse workload class. Neither result establishes a production chat or model inference improvement. No production activation occurred. The software timing and hardware roofline are distinct experiments.

Continuum steady heat flow and min-of-ceilings arithmetic suit the system screen. The software experiment needs exact discrete arithmetic. A mixture simplex would require a composite constitutive model. N-ality or fuzzy scores do not improve the acceptance tests.

## Replay

Install NumPy, then run from the repository root:

```sh
PYTHONPATH=python OPENBLAS_NUM_THREADS=1 python scripts/merlin/run_parallax_architecture.py OUTPUT
```

Inspect Frozen-Selection.json and Results.json. Timing winners may vary by host.
