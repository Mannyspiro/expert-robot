# Registered-terminal topology alternative B

This isolated candidate starts from PR178 commit
`584b948332b76596311d75133c0430d761e2f67a`. The renderer and default review
behavior are unchanged. It adds no dependency beyond the existing Pillow path.

Use `merlin.drafting_control.review_wiring(source, guide_dir, image,
verdict_file, destination, topology_check=True)` with this directory's `python`
on `PYTHONPATH`. The optional gate uses the already decoded PNG. It compares
eight-connected fixed-palette teal stroke components near registered terminals
against the canonical source's connected net groups, bridging the documented
white pin circle and gray outline. It never upgrades a supplied review verdict.

`result['topology_check']['status']` is one of:

| Status | Meaning | Effect on review |
| --- | --- | --- |
| `consistent_with_expected_connectivity` | Observed terminal partitions match source net groups within this narrow profile | Retain the existing review decision |
| `contradicted` | Missing terminal strokes, split expected nets, or joined separate nets | Reject |
| `abstain` | Unsupported canvas, scale/palette, no registered strokes, excessive ink, or substantial unassigned strokes | Reject pending independent review; diagnostic retains abstention |

This is a raster topology screen, not an image semantic reviewer or physical
wiring qualification. It does not authenticate the reviewer, read labels,
verify component geometry, infer junction semantics, or detect every extra
same-net branch. Nearby strokes can alias under pixel adjacency and pin-hole
bridging. Changed palettes and alignment are unsupported. A matching graph is
not proof of a correct diagram. The original independent visual checks remain
necessary. There is no qualification or promotion authority.

The public development checks cover branched connectivity and white pin holes,
broken/joined/missing conductors, unknown palette, wrong registration,
unassigned strokes, gray component lines, an explicitly undetected same-net
branch, and the end-to-end registered guide/default review path. All 17 tests
passed (7 copied baseline tests plus 10 new tests). `protocol.json` preserves
the pre-evaluation policy and its public-guide-only radius correction;
`freeze.json` records exact source hashes. No independent holdout inputs or
results were read while developing this candidate.

Run from the workspace root:

```sh
PYTHONPATH=daily20/arm_b/python python -m unittest discover -s daily20/arm_b/tests -v
```
