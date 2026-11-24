#!/usr/bin/env python3
"""Non-dispatching preflight. Run with python -I -B and a JSON request on stdin."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from wilborn_ops.security_monitoring_profile import main


if __name__ == "__main__":
    raise SystemExit(main())
