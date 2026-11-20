"""Pin every Python source used by each measured candidate."""
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("checkout", type=Path)
args = parser.parse_args()
directory = args.checkout / "python/merlin"
paths = sorted(directory.glob("drafting*.py")) + [directory / "wiring_sheet.py"]
pins = {str(path.relative_to(args.checkout)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
print(json.dumps(pins, indent=2))
