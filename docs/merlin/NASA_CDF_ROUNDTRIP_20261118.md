# Optional NASA-format CDF experiment

The local offline experiment completed on 2026-11-18 using **LASP CDFlib 1.3.16**, a separately maintained MIT-licensed Python implementation of NASA's CDF scientific format. The NASA native CDF library was neither installed nor executed. Existing NumPy 2.3.5 was used with Python 3.12.14 on Linux x86-64. This is not OCI, Python 3.9 execution, independent NASA-library interoperability, or production qualification.

## Measured results

| Fixed fixture / mode | Result |
|---|---|
| Samples | 4,096 synthetic records; CDF TT2000 integer time coordinate at 128 Hz, with no UTC conversion claim |
| Numeric variables | Scalar volts, three-component vector metres, scalar uncertainty, time and uint8 validity mask |
| Missing values | Three invalid sample indices, finite FILLVAL metadata and an explicit mask; valid zero values remain distinct |
| Uncompressed CDF | 241,453 bytes |
| CDF variable-level gzip 6 | 35,430 bytes; file-level compression disabled in both modes |
| File-size ratio | 6.8149× for this intentionally regular fixture only |
| Recovery | All 40 recorded checks per file passed, including exact numeric values/types/shapes, normalized array-byte hashes, units, sample count, metadata and a fixed vector subset |
| Blank text | Empty global comment, empty sample note and two-space note recovered exactly in both files |
| Negative control | Same-length stored-checksum alteration rejected with OSError when validation was enabled |

The negative control checks CDF's stored MD5 integrity mechanism. It does not authenticate a source or establish scientific truth. The writer and reader are from the same library. The result does not establish broader format interoperability or hostile-file safety. Single timing samples are retained in the receipt but are not a performance benchmark. NaN values, Unicode strings and native NASA CDF cross-reading were not tested.

The fixture consists entirely of generated values. No private chat, learner record, remote scientific dataset or credentials were read or uploaded. No application dependency files, services or databases changed.

## Reproduce optionally

The script has no downloader or installer. It requires CDFlib 1.3.16 and NumPy in a caller-owned isolated environment, and refuses an existing output directory:

```sh
python scripts/merlin/measure_cdf_roundtrip.py --output-dir /tmp/merlin-cdf-new-run
```

For this measurement, one wheel download succeeded and was extracted into a private experiment directory, without installing anything. Its SHA-256 was checked against the primary PyPI page before use:

`54d3f525651e9293b65a71b29b6b0b737cfe8e8f2a9191dcb686d261b77fc4f1`

The optional script is Python 3.9 syntax compatible; only Python 3.12.14 was executed here. The measured receipt is `docs/evidence/nasa-cdf-roundtrip-20261118.json`; it binds the exact script, implementation modules, dependency wheel, fixture manifest and CDF file digests. The script writes its own reproducible receipt and manifest into the new output directory. Acquisition notes in the archived receipt describe this execution separately.

## Rights and proposed use

NASA's [CDF Python guide](https://cdf.gsfc.nasa.gov/quickstartguides/Python.html) identifies CDFlib as an independent pure-Python reader/writer. The selected [release](https://pypi.org/project/cdflib/1.3.16/) and [source license](https://github.com/lasp/cdflib/blob/cf7553fe93c0684ae461fffb1df0a0b9daa23219/LICENSE) identify LASP and the MIT license, copyright 2025 Regents of the University of Colorado. Preserve its copyright and permission notice when redistributing covered code. These terms are distinct from NASA's native CDF distribution terms. No external publishing-attestation verification or freedom-to-operate analysis was performed.

CDF looks viable as an **optional numeric scientific interchange artifact**. This fixture does not justify replacing existing formats or the canonical registry. Keep raw and derived files, scientific metadata and exact ArtifactRefs in the existing Merlin evidence path. The next discriminating gate would be native NASA-library cross-reading on a fixed real interchange requirement, with original bytes and negative results preserved.

Qualification and promotion authority remain false.
