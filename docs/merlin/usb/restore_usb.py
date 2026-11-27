"""Inspect or reconstruct the exact Merlin AI OS Xenomaths USB image."""
import argparse
from contextlib import ExitStack
from hashlib import file_digest, sha256
import gzip
import json
import os
from pathlib import Path
import tempfile
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "release.json"
LAYOUT = HERE / "recovery" / "ISO_Layout.json"
BUFFER = 4 * 1024 * 1024
LITERALS_MEMBER = "Merlin_AI_OS_Xenomaths_Recovery/ISO_Literals.gz"


def check_file(handle, spec, label):
    if handle.seek(0, os.SEEK_END) != spec["bytes"]:
        raise ValueError(f"{label}: file size does not match the release")
    handle.seek(0)
    if file_digest(handle, "sha256").hexdigest() != spec["sha256"]:
        raise ValueError(f"{label}: SHA-256 does not match the release")
    handle.seek(0)


def verify(path, spec):
    with path.open("rb") as source:
        check_file(source, spec, str(path))
    print(f"Verified {path.name}: {spec['sha256']}")


def restore(args, info):
    plan = json.loads(LAYOUT.read_text())
    if plan["sha256"] != info["iso"]["sha256"] or plan["bytes"] != info["iso"]["bytes"]:
        raise ValueError("The recovery layout does not match the release record")
    if plan["sources"] != {name: info[name]["sha256"] for name in ("base", "model")}:
        raise ValueError("The recovery layout names different base inputs")
    output = args.output
    if not args.verify_only and (output.suffix.lower() != ".iso" or output.exists()):
        raise ValueError("Choose a new .iso filename")
    temporary = None
    try:
        with ExitStack() as stack:
            archive = stack.enter_context(args.recovery.open("rb"))
            check_file(archive, info["recovery"], "Recovery ZIP")
            files = {name: stack.enter_context(getattr(args, name).open("rb"))
                     for name in ("base", "model")}
            for name, stream in files.items():
                check_file(stream, info[name], name)
            recovery = stack.enter_context(ZipFile(archive))
            member = stack.enter_context(recovery.open(LITERALS_MEMBER))
            literals = stack.enter_context(gzip.GzipFile(fileobj=member))
            writer = None
            if not args.verify_only:
                output.parent.mkdir(parents=True, exist_ok=True)
                writer = stack.enter_context(tempfile.NamedTemporaryFile(
                    dir=output.parent, prefix=".merlin-usb-", delete=False))
                temporary = Path(writer.name)
            written = 0
            receipt = sha256()
            for name, offset, count in plan["ranges"]:
                if name == "literal":
                    source = literals
                elif name in files:
                    source = files[name]
                    source.seek(offset)
                else:
                    raise ValueError(f"Unknown range source: {name}")
                while count:
                    data = source.read(min(count, BUFFER))
                    if not data:
                        raise ValueError(f"Truncated data from {name}")
                    if writer is not None:
                        writer.write(data)
                    receipt.update(data)
                    written += len(data)
                    count -= len(data)
            if (literals.read(1) or written != plan["bytes"]
                    or receipt.hexdigest() != plan["sha256"]):
                raise ValueError("Reconstructed ISO does not match the release")
        if temporary is not None:
            # Install a verified output without replacing a path created concurrently.
            os.link(temporary, output)
        label = "Verified reconstructed stream" if args.verify_only else f"Restored {output}"
        print(f"{label}: {receipt.hexdigest()}")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True)
    v = commands.add_parser("verify")
    v.add_argument("path", type=Path)
    v.add_argument("--artifact", choices=("iso", "recovery", "builder", "base", "model"), default="iso")
    r = commands.add_parser("restore")
    for arg in ("recovery", "base", "model"):
        r.add_argument(f"--{arg}", required=True, type=Path)
    r.add_argument("--output", type=Path, default=Path("Merlin_AI_OS_Xenomaths_x86_64.iso"))
    r.add_argument("--verify-only", action="store_true")
    args = cli.parse_args()
    info = json.loads(MANIFEST.read_text())
    try:
        if args.command == "verify":
            verify(args.path, info[args.artifact])
        else:
            restore(args, info)
    except (ValueError, OSError, KeyError) as error:
        cli.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
