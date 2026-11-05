# Reproducible headless FreeCAD runtime for a separately approved worker.
# Build this image in the Avrea runner only after its operator has approved
# package installation and the runner's resource/network policy.
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    QT_QPA_PLATFORM=offscreen \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
      python3 \
      freecad-python3=0.20.2+dfsg1-4+deb12u1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/merlin
COPY verify_runtime.py /opt/merlin/verify_runtime.py
RUN python3 /opt/merlin/verify_runtime.py --check-only

RUN useradd --create-home --uid 10001 merlin \
 && mkdir -p /work/input /work/output \
 && chown -R merlin:merlin /work /opt/merlin
USER merlin

ENTRYPOINT ["python3", "/opt/merlin/verify_runtime.py"]
