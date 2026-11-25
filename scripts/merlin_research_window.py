#!/usr/bin/env python3
"""Run the visible research window without installing the package."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from merlin.research_window import main
if __name__ == "__main__":
    main()
