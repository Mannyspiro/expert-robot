"""Verify that an outgoing last frame matches an incoming first frame."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile


def boundaries(path):
    with tempfile.TemporaryFile(mode="w+t") as errors:
        cmd = ["ffmpeg","-nostdin","-v","error","-xerror","-i",str(path),"-map","0:v:0",
               "-vf","format=rgb24","-fps_mode","passthrough","-c:v","rawvideo","-threads","1",
               "-f","framehash","-hash","sha256","-"]
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errors, text=True) as child:
            first = last = size = None
            count = 0
            for raw in child.stdout:
                if raw.startswith("#dimensions"):
                    size = raw.partition(":")[2].strip()
                if not raw.startswith("#") and raw.strip():
                    checksum = raw.strip().rsplit(",", 1)[-1].strip()
                    if not re.fullmatch(r"[0-9a-f]{64}", checksum):
                        raise ValueError("Unexpected FFmpeg frame hash")
                    first = first or checksum
                    last = checksum
                    count += 1
            if child.wait() != 0 or count == 0 or not size:
                errors.seek(0)
                raise RuntimeError(f"Could not decode complete video {path.name}: {errors.read()[-1200:]}")
    return {"first":first,"last":last,"frames":count,"dimensions":size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outgoing", type=Path)
    parser.add_argument("incoming", type=Path)
    args = parser.parse_args()
    out, incoming = boundaries(args.outgoing), boundaries(args.incoming)
    match = out["dimensions"] == incoming["dimensions"] and out["last"] == incoming["first"]
    print(json.dumps({"match":match,"outgoing":out,"incoming":incoming},indent=2))
    raise SystemExit(0 if match else 2)


if __name__ == "__main__":
    main()
