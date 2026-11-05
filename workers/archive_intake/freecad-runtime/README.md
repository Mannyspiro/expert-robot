# FreeCAD runtime image for Merlin / Avrea

This directory defines a reproducible headless runtime image that an authorized Avrea worker operator can build and qualify. It does **not** install anything into a remote runner by itself and does not contact Avrea.

## Build and verify

From the repository root:

    docker build -f workers/archive_intake/freecad-runtime/Dockerfile -t merlin-freecad:debian-bookworm .

Then run the module probe with no model input:

    docker run --rm --network none merlin-freecad:debian-bookworm

The image pins Debian Bookworm's `freecad-python3` package to `0.20.2+dfsg1-4+deb12u1`. The build fails closed if the expected FreeCAD Python modules (`FreeCAD`, `Import`, `Part`, `Mesh`, `MeshPart`) cannot be imported. The probe does not import or execute CAD files.

## Avrea worker integration

An Avrea worker should use this image as an isolated geometry worker only after the provider has:
- approved the image and package installation;
- enforced CPU, memory, wall-clock, process-count and output-size limits outside Merlin;
- mounted input read-only and output to a dedicated writable directory;
- disabled network access during CAD processing;
- supplied an immutable task contract containing the input SHA-256, exact FreeCAD build, explicit units/frame and requested outputs;
- returned the output manifest and SHA-256 hashes for Merlin receipt validation.

Do not pass credentials into the CAD container. Do not mount the Docker socket, host home directory, Git credentials or unrelated project secrets. Keep the runner's network disabled for the processing phase. Container-level limits must be configured by Avrea/the host, not inferred from this Dockerfile.

## Current integration state

No Avrea connector/runner is available in this ChatGPT session, so this image has **not** been built, downloaded, uploaded, or dispatched to Avrea. The runtime version is pinned as a reproducibility target, not represented as installed or verified. The next operator step is to build this image in the authorized Avrea runner and report the image digest plus the module-probe result. Only then should Merlin enable the FreeCAD backend for real CAD jobs.
