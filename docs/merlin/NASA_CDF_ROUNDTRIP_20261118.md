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

The original experiment used CDFlib for writing and reading. Its checksum check detected the altered fixture. Timings cover one run per mode. NaN values and Unicode strings remain untested. The independent reader results below cover the two generated files.

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

CDF looks viable as an **optional numeric scientific interchange artifact**. This fixture does not justify replacing existing formats or the canonical registry. Keep raw and derived files, scientific metadata and exact ArtifactRefs in the existing Merlin evidence path. A representative instrument dataset with declared units, irregular sampling and Unicode metadata would broaden this fixed-fixture result.

Qualification and promotion authority remain false.

## Independent native reader

A second reader reopened both CDFlib outputs through SpacePy 0.7.0 and NASA's native CDF 3.9.1 library. All 24 checks passed for each file. They compare the original array bytes, types, shapes, units, missing indices, blank strings and fixture identity. The checks consume the original manifest, whose digest the script pins. The writer and independent reader ran on Linux x86-64.

After generating the files with the writer, run the following command in the separate reader environment.

```sh
python scripts/merlin/check_cdf_native_reader.py /tmp/merlin-cdf-new-run
```

The SpacePy Linux wheel used in this measurement has SHA-256 `61b160bb422e3a85dac2e5ee163d3f01112524d7f30da1d64ae839ebad7cbd27`. The wheel includes NASA's native library. [SpacePy documentation](https://spacepy.github.io/install_linux.html) · [Native-reader receipt](../evidence/nasa-cdf-native-read-20261118.json)
