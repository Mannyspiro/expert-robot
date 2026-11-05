# Reproducible headless FreeCAD runtime for a separately approved worker.
# Build from repository root; the worker operator controls host-level limits.
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    QT_QPA_PLATFORM=offscreen \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/merlin/archive_intake

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
      python3 \
      freecad-python3=0.20.2+dfsg1-4+deb12u1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/merlin
COPY workers/archive_intake /opt/merlin/archive_intake
RUN python3 /opt/merlin/archive_intake/freecad-runtime/verify_runtime.py --check-only

RUN useradd --create-home --uid 10001 merlin \
 && mkdir -p /work/input /work/output \
 && chown -R merlin:merlin /work /opt/merlin
USER 10001:10001

# Default invocation is a harmless module probe. Geometry jobs must explicitly
# override the command and mount a read-only input plus a separate output path.
ENTRYPOINT ["python3", "/opt/merlin/archive_intake/freecad-runtime/verify_runtime.py"]
