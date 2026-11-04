"""Merlin subsystem package with a shared path for the split source tree.

Core algebra modules live in the repository-level merlin/ directory; engineering,
proof and research modules live in python/merlin/. Extending the package path
keeps both import families available in one interpreter regardless of whether
the repository root or python/ is first on sys.path.
"""
from pathlib import Path

_here = Path(__file__).resolve().parent
_other = _here.parent / "python" / "merlin"
if _other.is_dir() and str(_other) not in __path__:
    __path__.append(str(_other))
