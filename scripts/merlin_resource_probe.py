#!/usr/bin/env python3
"""CLI entry point for Merlin's Avrea resource probe."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from merlin.resource_probe import main


if __name__ == "__main__":
    main()
