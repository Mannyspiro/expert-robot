#!/usr/bin/env python3
"""Probe the FreeCAD Python runtime without opening untrusted CAD inputs."""
from __future__ import annotations

import argparse
import importlib
import json
import pathlib
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    # Debian's FreeCAD packages keep modules outside the default interpreter
    # path. Add only known package locations that actually exist.
    roots = (
        pathlib.Path("/usr/lib/freecad/lib"),
        pathlib.Path("/usr/lib/freecad/Mod"),
        pathlib.Path("/usr/lib/freecad-python3/lib"),
        pathlib.Path("/usr/lib/freecad-python3/Mod"),
        pathlib.Path("/usr/lib/python3/dist-packages"),
    )
    for root in roots:
        if root.exists():
            sys.path.insert(0, str(root))

    modules = {}
    for name in ("FreeCAD", "Import", "Part", "Mesh", "MeshPart"):
        try:
            module = importlib.import_module(name)
            modules[name] = getattr(module, "__file__", "built-in")
        except Exception as exc:
            print(json.dumps({
                "status": "unavailable",
                "module": name,
                "error": type(exc).__name__ + ": " + str(exc),
            }, sort_keys=True), file=sys.stderr)
            return 2

    app = modules["FreeCAD"]
    print(json.dumps({
        "status": "ready",
        "python": sys.version.split()[0],
        "modules": modules,
        "note": "module import verified; no CAD model was imported or processed",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
