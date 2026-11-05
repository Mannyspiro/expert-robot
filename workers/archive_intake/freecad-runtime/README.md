# FreeCAD runtime image for Merlin / Avrea

This directory defines a reproducible headless runtime image for an authorized geometry worker. The image includes Merlin's geometry contract and the explicit FreeCAD adapter. It does **not** contact Avrea or bypass the provider's worker policy.

## Build and verify

From the repository root:

    docker build -f workers/archive_intake/freecad-runtime/Dockerfile -t merlin-freecad:debian-bookworm .

Run the harmless module probe:

    docker run --rm --network none merlin-freecad:debian-bookworm

The image pins Debian Bookworm's `freecad-python3` package to `0.20.2+dfsg1-4+deb12u1`. The build fails if the expected FreeCAD Python modules (`FreeCAD`, `Import`, `Part`, `Mesh`, `MeshPart`) cannot be imported. The probe does not import or execute CAD files.

## Run one geometry job

Prepare a dedicated input directory containing:
- `job.json`: a Merlin CAD Geometry Job Contract v1 request;
- the CAD file named by the request's relative `input_path`.

The request must bind the exact input bytes with `input_sha256`, state the input format, units, coordinate frame and requested outputs. Example request shape is defined by `schemas/cad-geometry-job-v1.schema.json`.

Mount input read-only and output as a separate writable directory. Example (adjust host paths and resource ceilings to the Avrea policy):

    docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --memory=2g --cpus=2 --pids-limit=128 --security-opt=no-new-privileges --cap-drop=ALL --user 10001:10001 --mount type=bind,src=/ABSOLUTE/PATH/input,dst=/work/input,readonly --mount type=bind,src=/ABSOLUTE/PATH/output,dst=/work/output --entrypoint python3 merlin-freecad:debian-bookworm /opt/merlin/archive_intake/freecad-runtime/run_geometry_job.py --request /work/input/job.json --input-root /work/input --output-dir /work/output

The runner validates the job through `cad_geometry_backend.execute_job`, verifies the input digest before processing, checks every returned output path and SHA-256, and atomically writes `geometry-receipt.json`. The input and output workspaces must be separate and non-nested. The runner returns a nonzero exit code on failed/inconclusive jobs.

The example resource flags are operator-selected ceilings, not proof of a complete sandbox. The host/Avrea worker must additionally enforce wall-clock timeout, process and output limits, filesystem policy and network isolation. Do not pass credentials into the CAD container. Do not mount the Docker socket, host home directory, Git credentials or unrelated project secrets. Keep the processing phase network-disabled.

## Avrea worker integration

An Avrea worker should use this image only after the provider has:
- approved the image and package installation;
- enforced CPU, memory, wall-clock, process-count and output-size limits outside Merlin;
- mounted inputs read-only and outputs to a dedicated writable directory;
- disabled network access during CAD processing;
- supplied an immutable task contract containing the input SHA-256, exact FreeCAD build, explicit units/frame and requested outputs;
- returned the image digest, runtime probe result, output manifest and SHA-256 hashes for Merlin receipt validation.

Merlin validates contracts and receipts; it cannot impose remote OS-level resource limits itself. No credentials belong in the CAD container.

## Current integration state

The repository now contains a runnable job entry point and mocked contract tests. The image has **not** been built, downloaded, uploaded or dispatched to Avrea in this session. No CAD model has been processed by a real FreeCAD runtime. The pinned version is a reproducibility target, not an installed/verified runtime. The next operator step is to build the image in the authorized worker, report the immutable image digest and module-probe result, then run a benign public fixture under strict external limits.

## Deterministic qualification fixture

`generate_fixture.py` creates a small three-solid test assembly inside the exact FreeCAD Python runtime:

- 20 × 10 × 2 mm base plate;
- 5 × 5 × 8 mm upper block;
- radius-2 mm, height-6 mm round post;
- nested native document groups (`MerlinAssembly` → `UpperSubassembly`);
- native `.FCStd`, neutral `.step`, and a SHA-256 fixture manifest.

The manifest records the declared units/frame, source component/group names, artifact hashes and analytic reference values:
- overall bounds: 20 × 10 × 10 mm;
- sum of source-solid volumes: (600 + 24\pi) mm³;
- sum of source-solid surface areas: (730 + 32\pi) mm².

These are analytic references for the generated primitives. They are not proof of STEP round-trip fidelity or independent CAD correctness. STEP export may flatten or alter assembly hierarchy; compare the native FCStd hierarchy and STEP geometry separately.

Use the generated STEP file as the input to a job contract with `input_format: "step"`, explicit units/frame, and requested outputs such as `topology_report`, `bounding_box`, `volume`, `surface_area`, and `mesh`. A mesh request must include positive finite `linear_deflection` and `angular_deflection` values. The geometry backend now rejects a declared format that does not match the actual extension and rejects missing/non-finite mesh tolerances.

The fixture generator and its mocked manifest test are committed but have not been executed in FreeCAD. The mocked test checks the generated manifest plumbing, not FreeCAD kernel behavior.
