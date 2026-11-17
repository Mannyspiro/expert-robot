# Private OCI tool host

`dot_ai_os.private_runtime` provides a persistent local tool process and a bounded CLI client over a Linux Unix-domain socket. The fixed trusted GitHub-to-OCI route can call it without a public endpoint, OAuth issuer or pasted secret. It is not a direct ChatGPT remote MCP connection.

The host authenticates kernel-reported Linux UIDs using `SO_PEERCRED`, plus socket filesystem permissions. A UID is not a GitHub workflow identity. Any process running under an allowed shared runner UID has that UID's grants. Give shared runners only read-only reviewed engineering/demo tools; do not grant request mutation or expose raw private chat state to that UID.

The default CLI host exposes only explicitly granted context health/search/fetch/handoff/RSI-status tools. `--simulation-demo` additionally registers the fixed reviewed `virtual_circuit_demo`; its only arguments are `{}` or `{"operation":"demo"}`. No caller-named plugin, shell, command, file path, source import, model/provider, network or runner operation is accepted. The demo reports an ideal linear DC circuit comparison, wiring/SPICE text and an OpenSCAD box preview. It does not run FreeCAD or ngspice, certify hardware, independently verify through CACE or promote a candidate.

## Runtime and files

The runtime uses standard-library Python only. It parses under Python 3.9 grammar and is intended for the observed OCI Python 3.9.25/SQLite 3.34.1 host; actual host tests are required before enabling a service. Local selected-module tests run under Python 3.12.14. No MCP, HTTP, FreeCAD, ngspice or model dependency is required for this route.

Required package files are `dot_ai_os/__init__.py`, `bridge.py`, `dual_coder.py`, `job_inbox.py`, `private_runtime.py` and, for the static demo flag, `simulation_research.py`. Canonical dependencies are the pinned expert-robot `merlin/__init__.py`, `artifact_ref.py`, `project_registry.py` and `engineering_ir.py`. Put their parent directories on `PYTHONPATH`; the deployment manifest must identify exact source commits and file digests.

Use a dedicated `merlin-dot` service identity. A private runtime directory may be owned by `merlin-dot`, group `opc`, mode `0750`; the socket is created as `0660`. The client verifies the expected service UID after connecting. The runtime directory must not be group/other writable. The config must be a regular non-symlink file, owned by root or the service UID, not group/other writable and at most 16 KiB.

Provision a separate existing engineering/demo-only canonical registry. The host does not create a project, ingest sources or copy any current chat-state database. Its read-only registry refuses WAL mode to avoid creating SQLite sidecars; publish a consistent non-WAL read snapshot through the operator workflow.

Configuration schema:

```json
{
  "schema": "merlin-private-host/1",
  "project_id": "engineering-demo",
  "namespaces": ["merlin"],
  "grants": [
    {
      "uid": 1000,
      "principal": "unix:reviewed-engineering-reader",
      "tools": ["health", "context_status", "context_search", "context_fetch", "virtual_circuit_demo"]
    }
  ]
}
```

The UID above illustrates the schema; obtain the actual account UID from the host rather than assuming it is 1000. Tool grants are explicit, without wildcards. The CLI has no pending-inbox enable flag. A separate reviewed embedding host would need to supply an inbox and grant `job_submit` to a separately trusted principal; do not use a shared runner UID for that mutation path.

## Calls and validation

The service command shape is:

```bash
/usr/bin/python3 -m dot_ai_os.private_runtime serve --root /var/lib/merlin-dot-private/state --socket /run/merlin-dot-private/tools.sock --config /etc/merlin-dot-private/config.json --simulation-demo
```

A fixed job sends bounded JSON on stdin to:

```bash
/usr/bin/python3 -m dot_ai_os.private_runtime call --socket /run/merlin-dot-private/tools.sock --server-uid SERVICE_UID
```

Example request:

```json
{"schema":"merlin-private-call/1","request_id":"demo-001","tool":"virtual_circuit_demo","arguments":{"operation":"demo"}}
```

The wire protocol is a four-byte big-endian length followed by UTF-8 JSON: maximum 32 KiB request and 64 KiB response. Unknown/duplicate fields, non-finite JSON numbers, deep structures, ungranted tools and oversized results are rejected. Each connection handles one call with a five-second frame-read timeout; the server is sequential with a bounded listen backlog. No input or source body is written to service logs.

Run `python -m unittest discover -s tests -p test_private_runtime.py -v` on the OCI host. Tests include real socket peer credentials, the CLI subprocess, namespace isolation, read-only SQLite behavior, hostile frames and server identity checks. In the current local workspace, AF_UNIX creation returns EPERM: ten real-socket tests therefore skip explicitly, while six direct/configuration tests pass. A local skipped result does not establish transport readiness. Enable the persistent service only after the actual-host socket tests and fixed-route health/demo calls succeed.

The supplied systemd template is a deployment candidate. Parent deployment tooling must adapt versioned source paths, preserve existing services/state and validate the observed UID/config/snapshot before installation.
