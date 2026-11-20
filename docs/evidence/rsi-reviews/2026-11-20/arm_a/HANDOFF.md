# Registered raster check — isolated arm A, November 20

This candidate adds an **opt-in** measurement of unexplained dark ink outside a source-reconstructed guide. It can withhold a drawing even when a correctly bound reviewer record falsely reports every check passed. The default workflow remains unchanged.

Call `review_wiring(source, guide_dir, image, verdict_file, destination, independent_raster=True)`. The result adds `raster_check`; only `clear_within_scope` can retain the existing human acceptance. `unexpected_stroke` and `unknown` reject. A clean measurement cannot override an uncertain human verdict. No CLI or production workflow was changed.

Source is Expert Robot PR178 at `584b948332b76596311d75133c0430d761e2f67a`, drafting Git blob `0fc229b3669f1fb5303d7ecae44774c00af72c0e`. Source files were checked against pinned Git blob identities. `candidate-freeze.json` freezes the two implementation files and development tests before the independent evaluation. `candidate.patch` contains the complete three-file change. `result.json` records commands, environment, observations and limits.

## Measured results

| Check | Result |
|---|---|
| New development raster checks | 11 passed, zero skips |
| Existing drafting contract | 3 passed, zero skips |
| Adjacent wiring sheet | 4 passed, zero skips |
| Independent fresh frozen dispositions | 4/4 versus baseline 2/4, reported by evaluator |
| Independent source review by coder B | No concrete blocker within stated scope |
| Python 3.9 | Grammar parsed; not executed |

Development covers exact-guide and light-tone positives, standalone/route-attached strokes, short ambiguous ink, missing content, registration shift, transparent/rescaled input, resource ceilings and guide scope. The false all-pass development record accepts by default and rejects with this measurement enabled. Fresh held-out files were not opened by coder A, and no candidate bytes changed after evaluation feedback.

The independent evaluator reports both registered/tinted positive cases accepted and both altered drawings withheld. The interrupted-wire case was withheld as `unexpected_stroke`; this is a correct conservative disposition, **not evidence of general gap detection or correct fault classification**. Four synthetic cases are insufficient to qualify a visual checker.

Actual environment: Python 3.12.14, Pillow 13.0.0, supported Inkscape 1.4 fallback. CairoSVG is unavailable. Installed ezdxf is 1.4.5, whereas the repository requirement is 1.4.4; the adjacent tests do not establish the exact pinned dependency profile. Coder A installed no packages.

## Measurement and uncertainty

The helper uses fixed luminance threshold 160, a three-pixel expansion of guide ink, fixed two-pixel registration tolerance, and bounded connected components with long axis-aligned runs. Thresholds were recorded before execution; they are not optimized against a candidate image. Every measurement binds guide, candidate and source hashes; source reconstruction remains the caller's prerequisite.

A long residual is **unmodeled ink**, not proof of a conductor or a named electrical connection. Added annotation or texture may trigger review. Short, faint, overlapping or near-guide changes can evade detection. A three-pixel corridor can hide a small connection or junction. Ambiguous residuals, registration/content loss and exhausted resource budgets abstain. There is no OCR, terminal graph, netlist extraction, general wire-break classification or absence proof. Human review remains necessary; physical/electrical qualification and promotion authority remain false.

Next, preregister new short-bridge/pin-gap/rotation/annotation controls and measure exact terminal adjacency independently. Preserve null cases and false alarms. Keep this arm opt-in until broader tests justify any adoption. Roll back by discarding this isolated patch; no remote write, runner dispatch, deployment or live service change occurred.
