#!/usr/bin/env python3
"""Bind the actual pinned CPU build configuration to its runtime requirements."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import shlex
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portable/merlin_studio"))
from linux_preflight import CPU_BASELINES, REQUIREMENTS_SCHEMA


def configuration(build_directory, target, engine_sha256, python_sha256):
    if target not in CPU_BASELINES or any(not re.fullmatch(r"[0-9a-f]{64}", value)
                                         for value in (engine_sha256, python_sha256)):
        raise ValueError("invalid target or executable identity")
    directory = Path(build_directory)
    cache_bytes = (directory / "CMakeCache.txt").read_bytes()
    commands_bytes = (directory / "compile_commands.json").read_bytes()
    if len(cache_bytes) > 1024**2 or len(commands_bytes) > 16 * 1024**2:
        raise ValueError("build configuration exceeds bound")
    cache = {}
    for line in cache_bytes.decode().splitlines():
        match = re.fullmatch(r"([A-Z][A-Z0-9_]*):(?:BOOL|STRING)=(.*)", line)
        if match and (match[1].startswith(("GGML_", "LLAMA_")) or match[1] == "BUILD_SHARED_LIBS"):
            cache[match[1]] = match[2]
    for key in ("GGML_NATIVE", "GGML_CUDA", "GGML_VULKAN", "LLAMA_BUILD_UI", "LLAMA_USE_PREBUILT_UI", "BUILD_SHARED_LIBS"):
        if cache.get(key) != "OFF":
            raise ValueError("required isolated CPU build option differs: " + key)
    commands = json.loads(commands_bytes)
    flags = set()
    cpu_sources = 0
    for row in commands:
        words = row.get("arguments") or shlex.split(row["command"])
        if "-march=native" in words or "-mcpu=native" in words:
            raise ValueError("host-native instruction flags are forbidden")
        if "ggml-cpu/" in row["file"]:
            cpu_sources += 1
            flags.update(word for word in words if word.startswith((
                "-march=", "-mcpu=", "-msse", "-mavx", "-mamx", "-mbmi", "-mf16", "-mfma")))
    wanted = ({"-msse4.2", "-mavx", "-mavx2", "-mbmi2", "-mf16c", "-mfma"}
              if target == "linux-x86_64" else {"-march=armv8-a"})
    if cpu_sources == 0 or flags != wanted:
        raise ValueError("actual CPU compile flags differ from declared baseline")
    if target == "linux-aarch64" and cache.get("GGML_CPU_ARM_ARCH") != "armv8-a":
        raise ValueError("ARM baseline declaration differs")
    readelf = subprocess.run(["readelf", "-d", str(directory / "bin/llama-server")],
                             capture_output=True, text=True, check=True, timeout=5)
    if len(readelf.stdout) > 65536:
        raise ValueError("dynamic dependency metadata exceeds bound")
    libraries = sorted(set(re.findall(r"\(NEEDED\).*?\[([A-Za-z0-9_.+-]+)\]", readelf.stdout)))
    baseline, features = CPU_BASELINES[target]
    requirements = {"schema": REQUIREMENTS_SCHEMA, "platform": target,
                    "cpu_baseline": baseline, "cpu_features": features,
                    "engine_sha256": engine_sha256, "python_sha256": python_sha256,
                    "system_libraries": libraries, "build_libc": list(platform.libc_ver())}
    evidence = {"schema": "merlin-linux-build-configuration/1", "requirements": requirements,
                "cpu_source_count": cpu_sources, "cpu_compile_flags": sorted(flags),
                "cmake_options": cache, "cmake_cache_sha256": hashlib.sha256(cache_bytes).hexdigest(),
                "compile_commands_sha256": hashlib.sha256(commands_bytes).hexdigest(),
                "build_host_architecture": platform.machine(), "gpu_enabled": False,
                "embedded_upstream_ui_enabled": False}
    return requirements, evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-directory", type=Path, required=True)
    parser.add_argument("--target", required=True, choices=sorted(CPU_BASELINES))
    parser.add_argument("--engine-sha256", required=True)
    parser.add_argument("--python-sha256", required=True)
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    requirements, evidence = configuration(args.build_directory, args.target, args.engine_sha256, args.python_sha256)
    for path, value in ((args.requirements, requirements), (args.evidence, evidence)):
        with path.open("x") as output:
            json.dump(value, output, sort_keys=True, indent=2)
            output.write("\n")


if __name__ == "__main__":
    main()
