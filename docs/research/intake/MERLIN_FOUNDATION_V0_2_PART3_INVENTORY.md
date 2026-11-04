# Merlin Foundation v0.2 — Part 3 intake inventory

**Source file:** `MERLIN_Foundation_v0.2_Part3_of_3.zip`  
**Archive SHA-256:** `ddab71f63cc5c819e0e3c35fe43508825c3bdd1ef1b8d2e4d63af37979e7dba4`  
**Compressed size:** 232,193,572 bytes  
**Uncompressed object bytes:** 284,744,822  
**Outer objects:** 1,088

## Integrity result

All 1,088 outer objects were checked against their content-addressed SHA-256 path. All 42 embedded ZIP archives passed their ZIP CRC checks. No outer-object hash mismatch or nested ZIP CRC failure was found.

The ZIP is a content-addressed object store, not a normal directory archive. Original file names are recoverable only from embedded archives, internal manifests, or source metadata. Do not invent original paths for standalone objects.

| Detected outer-object type | Count |
|---|---:|
| Text | 693 |
| JSON | 193 |
| PNG | 57 |
| ZIP | 42 |
| Binary / other | 75 |
| HTML | 12 |
| JPEG | 11 |
| PDF | 4 |
| Gzip | 1 |
| **Total** | **1,088** |

## Embedded archive inventory

The 42 nested ZIPs contain 4,881 file entries and 4,228 distinct internal paths (repeated versioned snapshots account for the difference).

| Main archive family | Evidence from contents |
|---|---|
| Merlin v11 | 871 entries. README identifies a local-first Merlin × Hermes × CACE–MCFC research studio. Includes the reasoning/formal/geometry core, studio UI, optional local model bridge, research context, CAD/drafting/media tools, and MCFC/CACE research milestones. |
| CACE VRE v0.1–v0.13 | Versioned source snapshots are present. |
| CACE VRE folder `cace-studio-vre-v3.21` | 954 entries. **Internal version metadata conflicts:** `pyproject.toml` reports 0.76.0, README identifies v0.76, and `RELEASE_MANIFEST.json` identifies release 1.0 with source baseline v0.76. Treat the folder name as an archive label, not a reliable software version. |
| Merlin/Hermes/CACE/MCFC unified bundle | Three nested archives with 144, 110, and 101 entries; preserve as distinct source snapshots until lineage is reconciled. |
| Research iteration source tree | 314 manifest-listed research artifacts. Manifest explicitly scopes itself to local research artifacts, not complete production source. Includes Merlin iteration batches, MCFC/CACE milestones 44–120, LGM batches, modular atlas, geometric automata, spectral glyph and online spectral batches. |
| Merlin research miner v17 | 32 entries; evidence-first NASA/GitHub research and teaching-model scaffold. |
| Hermes lite v18 | 25 entries; thin Hermes skill integration over the v17 research miner, not a bundled Hermes runtime. |
| Hermes research miner v19 | 15 entries; source-revision pinning, evidence hashes, rights-aware metadata and local teaching-model scaffold. |
| Merlin/CACE context package v3 | 38 entries; project handoffs, context coverage audit, merit register, topic graph, SQLite context store, bridge and RSI sources. |
| Other engineering assets | Includes CAD/drafting SVG/DXF/SCAD examples, OBJ/STL geometry, photonic crystal concept mesh, visual assets, handoff documents and recovery bundles. |

## Engineering facts relevant to the current integration

1. The Merlin v11 README explicitly limits its freehand engineering board to a sketch/design tool and its 3D modeler to parametric concept geometry. It does not claim industrial CAD constraint solving, tolerance-certified CAD or STEP output.
2. The same README describes actual local APIs for plan, experiment, growth, CAD, draft-video, solid, image, video, ComfyUI, assistant and literature workflows. These are source-snapshot capabilities; they are not evidence that those endpoints are deployed in the current Expert Robot repository.
3. The CACE v3.21-labelled archive contains a module registry, typed graph executor, verification records and run certificates. Its executor validates graph node/port/type consistency and cycles; verifier records distinguish PASS, FAIL and NOT_RUN. The release metadata explicitly says general reliability is not formally verified.
4. CACE verification results and Merlin numerical/simulation results must remain distinct evidence classes. A passed software test does not prove physical device performance, manufacturability or a theorem.
5. The MCFC/CACE iteration folders include reports, result JSON, verifier scripts and red/green logs. They should be imported as separate provenance-bearing research records, not flattened into one asserted result.

## Recommended canonical reconstruction

- **Project identity:** use stable project IDs independent of archive folder names.
- **Source snapshots:** preserve each nested archive SHA-256, internal manifest, source path and observed version labels.
- **Deduplication:** deduplicate identical file content by SHA-256 while retaining every source-path occurrence.
- **Lineage:** connect versioned snapshots only when manifests, commit identifiers or file-level diffs support the relationship.
- **Evidence:** keep source assertion, static inspection, test result, numerical result, formal proof and physical measurement as separate typed states.
- **CACE adapter:** read-only import first; map module metadata, ports, graph edges, verifier records and run certificates into Merlin's registry/evidence model. Do not execute imported modules during intake.
- **CAD/MCFC:** treat assembly frames, part frames, board frames, connector/pin frames, route geometry and electrical-net topology as separate linked views of one engineering object. Geometry proposals remain non-manufacturing-qualified until independent checks are recorded.

## Intake status

- Outer object inventory: **HASH_VERIFIED**
- Nested ZIP CRC checks: **PASS**
- Internal project/file lineage: **PARTIALLY_RECONSTRUCTED**
- CACE release identity: **VERSION_LABEL_CONFLICT**
- Full source execution/qualification: **NOT_RUN**
- Fabrication or physical qualification: **NOT_CLAIMED**

This record covers Part 3 only. It must be combined with the inventories for Parts 1 and 2 before declaring Foundation v0.2 intake complete.
