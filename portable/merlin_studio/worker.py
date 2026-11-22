"""Approved Python worker with resource limits; this is not an OS sandbox."""
import os
import runpy
import sys

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Expected one script path")
    # Make direct worker invocations safe even if the parent omits -B:
    # a tight RLIMIT_FSIZE must never leave an incomplete import cache.
    sys.dont_write_bytecode = True
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
        resource.setrlimit(resource.RLIMIT_FSIZE, (128 * 1024, 128 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    except ImportError:
        pass
    script = os.path.abspath(sys.argv[1])
    sys.argv = [script]
    runpy.run_path(script, run_name="__main__")
