#!/usr/bin/env python3
"""Two or more networked CACE/PySCF quantum workers (localhost proof of concept).

Mode --worker: authenticated HTTP on 127.0.0.1, one CACE checkout/process.
Mode --coordinate: launch TWO separate CACE checkouts in distinct processes,
dispatch independent Hartree-Fock basis tasks simultaneously, attest input
hashes and worker identities, and merge results in deterministic order.

Never bind a public network interface. For different physical machines,
use an authenticated encrypted tunnel/mTLS design before enabling remote URLs.
CACE modules are initialized and actually execute a small FEM mesh sanity
check on each worker; PySCF currently performs the quantum calculations.
This is not a distributed SCF solver and is not a physics certificate.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import hmac
import importlib.util
import json
import math
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACE_PIN = "0e7aa229d3bb57174e281b883ee8af5445f15f75"
BASIS = ("sto-3g", "6-31g")
MAX_BODY = 1024 * 1024


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def load_quantum():
    path = ROOT / "scripts" / "evaluate_molecular_quantum.py"
    spec = importlib.util.spec_from_file_location("quantum_worker_baseline", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("missing quantum engine")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cace_identity(cace_root, expected_pin):
    """Prove separate worker imported and ran pinned CACE FEM, not just PySCF."""
    path = Path(cace_root).resolve(strict=True)
    actual = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True, text=True, capture_output=True, timeout=10,
    ).stdout.strip()
    if actual != expected_pin:
        raise ValueError("CACE checkout not at explicitly pinned commit")
    sys.path.insert(0, str(path))
    try:
        from cace_studio.modules.fem_nd import SimplexMeshND
        result = SimplexMeshND().execute(
            {}, {"vertices": [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]],
                 "elements": [[0, 1, 2]]}, {},
        )
        if "mesh" not in result or not result["mesh"]["vertices"]:
            raise RuntimeError("CACE FEM module sanity check failed")
    finally:
        sys.path.remove(str(path))
    return actual


def mac_of(token, data):
    return hmac.new(token.encode("utf-8"), canonical(data),
                    hashlib.sha256).hexdigest()


def run_basis_job(job, worker_id, cace_commit, token):
    graph = job["matter_graph"]
    job_id = job["job_id"]
    basis = job["basis"]
    if not isinstance(job_id, str) or not (1 <= len(job_id) <= 128):
        raise ValueError("invalid job ID")
    if basis not in BASIS:
        raise ValueError("basis not qualified for networked quantum route")
    if sha(graph) != job["expected_input_sha256"]:
        raise ValueError("quantum input hash mismatch")
    quantum = load_quantum().baseline(graph, bases=(basis,))
    if len(quantum["scf_results"]) != 1:
        raise ValueError("worker generated unexpected number of quantum results")
    if quantum["input_graph_sha256"] != job["expected_input_sha256"]:
        raise ValueError("worker quantum output input mismatch")
    result = {
        "job_id": job_id,
        "worker_id": worker_id,
        "cace_commit": cace_commit,
        "input_graph_sha256": job["expected_input_sha256"],
        "basis": basis,
        "quantum": quantum,
    }
    return {"result": result, "attestation_hmac": mac_of(token, result)}


def worker(port, worker_id, cace_root, cace_pin):
    token = os.environ.get("CACE_QUANTUM_TOKEN")
    if not token or len(token) < 40:
        raise RuntimeError("ephemeral quantum worker token missing")
    commit = cace_identity(cace_root, cace_pin)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return  # No credentials, payloads or molecular data in access log.

        def respond(self, code, data):
            payload = canonical(data)
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def permitted(self):
            return hmac.compare_digest(
                self.headers.get("X-CACE-Quantum-Token", ""), token
            )

        def do_GET(self):
            if not self.permitted():
                return self.respond(403, {"error": "unauthorized"})
            if self.path != "/health":
                return self.respond(404, {"error": "not_found"})
            return self.respond(200, {
                "worker_id": worker_id, "cace_commit": commit,
                "service": "cace_quantum_worker_v1",
                "quantum_backend": "PySCF RHF",
                "cace_fem_initialized": True,
            })

        def do_POST(self):
            if not self.permitted():
                return self.respond(403, {"error": "unauthorized"})
            if self.path != "/task":
                return self.respond(404, {"error": "not_found"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_BODY:
                    raise ValueError("payload size outside permitted range")
                job = json.loads(self.rfile.read(size))
                data = run_basis_job(job, worker_id, commit, token)
                return self.respond(200, data)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                return self.respond(422, {"error": "invalid_or_unqualified_job"})
            except Exception:
                return self.respond(500, {"error": "worker_calculation_failed"})

    server = HTTPServer(("127.0.0.1", port), Handler)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()


def http_json(url, token, payload=None, timeout=60):
    data = canonical(payload) if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "X-CACE-Quantum-Token": token,
            "Content-Type": "application/json",
        },
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(MAX_BODY + 1)
        if len(raw) > MAX_BODY:
            raise ValueError("worker output exceeds bounded response size")
        return json.loads(raw)


def unused_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_workers(cace_roots, token, cace_pin):
    if len(cace_roots) < 2 or len(cace_roots) > 4:
        raise ValueError("this bounded cluster supports 2..4 workers")
    if len({str(Path(x).resolve()) for x in cace_roots}) != len(cace_roots):
        raise ValueError("each worker needs a distinct CACE checkout")
    processes = []
    ports = set()
    env = dict(os.environ)
    env.update({
        "CACE_QUANTUM_TOKEN": token,
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "PYSCF_MAX_MEMORY": "384",
    })
    try:
        for i, root in enumerate(cace_roots):
            port = unused_port()
            while port in ports:
                port = unused_port()
            ports.add(port)
            process = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()),
                 "--worker", "--port", str(port),
                 "--worker-id", f"cace-{i+1}",
                 "--cace-root", str(root),
                 "--cace-pin", cace_pin],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
            processes.append((f"cace-{i+1}", port, process))
        deadline = time.monotonic() + 45
        pending = list(processes)
        while pending and time.monotonic() < deadline:
            for worker_entry in pending[:]:
                wid, port, process = worker_entry
                if process.poll() is not None:
                    raise RuntimeError(f"CACE worker {wid} could not initialize")
                try:
                    health = http_json(
                        f"http://127.0.0.1:{port}/health", token, timeout=2
                    )
                except (urllib.error.URLError, ConnectionError, TimeoutError):
                    continue
                if (health["worker_id"] != wid or
                    health["cace_commit"] != cace_pin or
                    health["cace_fem_initialized"] is not True):
                    raise ValueError("CACE worker identity/provenance failure")
                pending.remove(worker_entry)
            if pending:
                time.sleep(0.2)
        if pending:
            raise TimeoutError("CACE worker startup timeout")
        return processes
    except Exception:
        terminate_workers(processes)
        raise


def terminate_workers(processes):
    for _, _, p in processes:
        if p.poll() is None:
            p.terminate()
    for _, _, p in processes:
        try:
            p.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
            p.communicate()


def merge_results(graph, answers, token, pin):
    if len(answers) != len(BASIS):
        raise ValueError("basis work count incorrect")
    expected_hash = sha(graph)
    by_basis = {}
    worker_ids = set()
    for answer in answers:
        record = answer["result"]
        if not hmac.compare_digest(answer["attestation_hmac"],
                                   mac_of(token, record)):
            raise ValueError("worker response authentication failed")
        basis = record["basis"]
        if (record["cace_commit"] != pin or
            record["input_graph_sha256"] != expected_hash or
            record["quantum"]["input_graph_sha256"] != expected_hash or
            basis not in BASIS or basis in by_basis or
            record["worker_id"] in worker_ids or
            record["job_id"] != "quantum:" + basis):
            raise ValueError("duplicate or inconsistent quantum worker result")
        result = record["quantum"]["scf_results"]
        if (len(result) != 1 or result[0]["basis"] != basis or
            result[0]["converged"] is not True or
            not math.isfinite(result[0]["total_electronic_energy_hartree"])):
            raise ValueError("unqualified distributed RHF result")
        by_basis[basis] = result[0]
        worker_ids.add(record["worker_id"])
    if set(by_basis) != set(BASIS):
        raise ValueError("missing basis calculation")
    ordered = [by_basis[x] for x in BASIS]
    if ordered[1]["basis_functions"] <= ordered[0]["basis_functions"]:
        raise ValueError("inconsistent basis function counts")
    return {
        "schema_version": 1,
        "experiment_id": graph["matter_id"],
        "cace_source_commit": pin,
        "worker_count": len(worker_ids),
        "distinct_cace_worker_processes": True,
        "network_transport": "authenticated_loopback_http",
        "input_graph_sha256": expected_hash,
        "scf_results": ordered,
        "basis_energy_difference_hartree": (
            ordered[1]["total_electronic_energy_hartree"] -
            ordered[0]["total_electronic_energy_hartree"]
        ),
        "calculation_backend": "PySCF RHF (CACE orchestrated)",
        "cace_role": "separate verified FEM-capable worker instances and work scheduler",
        "distributed_single_scf": False,
        "readiness": {
            "computational_multiworker_baseline": True,
            "basis_limit_converged": False,
            "independent_electronic_methods_agree": False,
            "molecular_stability_certified": False,
            "production_release": False,
        },
        "evidence_ceiling": "networked_parallel_independent_basis_jobs_not_distributed_scf_or_synthesis",
    }


def coordinate(graph, cace_roots, pin, verify_serial=False):
    token = os.urandom(32).hex()
    processes = start_workers(cace_roots, token, pin)
    jobs = [
        {
            "job_id": "quantum:" + basis,
            "basis": basis,
            "matter_graph": graph,
            "expected_input_sha256": sha(graph),
        }
        for basis in BASIS
    ]
    try:
        started = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(
                    http_json,
                    f"http://127.0.0.1:{processes[i][1]}/task",
                    token, job, 120,
                )
                for i, job in enumerate(jobs)
            ]
            answers = [f.result(timeout=125) for f in futures]
        elapsed = time.perf_counter() - started
        result = merge_results(graph, answers, token, pin)
        result["parallel_task_wall_seconds"] = elapsed
        if verify_serial:
            serial = load_quantum().baseline(graph)
            errors = [
                abs(a["total_electronic_energy_hartree"] -
                    b["total_electronic_energy_hartree"])
                for a, b in zip(result["scf_results"], serial["scf_results"])
            ]
            result["serial_replay"] = {
                "passed": max(errors) <= 1e-7,
                "max_absolute_energy_delta_hartree": max(errors),
                "reference_backend": "same PySCF RHF (same implementation; not independent method)",
            }
            if not result["serial_replay"]["passed"]:
                raise ValueError("distributed-to-serial replay disagreement")
        return result
    finally:
        terminate_workers(processes)


def main():
    p = argparse.ArgumentParser()
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--worker", action="store_true")
    mode.add_argument("--coordinate", action="store_true")
    p.add_argument("--port", type=int)
    p.add_argument("--worker-id")
    p.add_argument("--cace-root")
    p.add_argument("--cace-roots", nargs="+")
    p.add_argument("--cace-pin", default=CACE_PIN)
    p.add_argument("--graph", type=Path)
    p.add_argument("--verify-serial", action="store_true")
    p.add_argument("-o", "--output", type=Path)
    args = p.parse_args()
    if args.worker:
        if not args.port or not args.worker_id or not args.cace_root:
            p.error("worker requires port, worker-id and cace-root")
        worker(args.port, args.worker_id, args.cace_root, args.cace_pin)
        return
    if not args.graph or not args.cace_roots or not args.output:
        p.error("coordinator requires graph, 2+ CACE roots, and output")
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    result = coordinate(graph, args.cace_roots, args.cace_pin,
                        args.verify_serial)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "experiment_id": result["experiment_id"],
        "worker_count": result["worker_count"],
        "parallel_task_wall_seconds": result["parallel_task_wall_seconds"],
        "basis_energy_difference_hartree":
            result["basis_energy_difference_hartree"],
        "serial_replay": result.get("serial_replay"),
        "evidence_ceiling": result["evidence_ceiling"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
