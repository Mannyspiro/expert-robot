"""Print or launch a contained QEMU workstation with the pinned Merlin image."""

import argparse
from hashlib import file_digest
import json
from pathlib import Path
import shutil
import subprocess


PINNED = "66b370c1d10d58cac54fbedd35c92ec1d6bb63318e15c83ebf8669c50fb19043"


def qemu_path(path):
    name = str(path.resolve(strict=True))
    if "," in name or "\n" in name:
        raise ValueError("QEMU image paths may not contain a comma or newline")
    return name


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("iso", type=Path)
    p.add_argument("--vcpus", type=int, default=4)
    p.add_argument("--ram-mib", type=int, default=4096)
    p.add_argument("--engine", choices=("tcg","kvm"), default="tcg")
    p.add_argument("--project-disk", type=Path, help="Optional existing QCOW2 project disk")
    p.add_argument("--launch", action="store_true")
    opts = p.parse_args()
    if not 1 <= opts.vcpus <= 32 or not 1024 <= opts.ram_mib <= 65536:
        p.error("Use 1–32 vCPUs and 1024–65536 MiB")
    image = qemu_path(opts.iso)
    command = [shutil.which("qemu-system-x86_64") or "qemu-system-x86_64",
               "-machine", "q35", "-accel", opts.engine, "-cpu", "host" if opts.engine == "kvm" else "max",
               "-smp", str(opts.vcpus), "-m", str(opts.ram_mib), "-boot", "d",
               "-drive", f"file={image},format=raw,media=cdrom,readonly=on", "-nic", "none"]
    if opts.project_disk:
        disk = qemu_path(opts.project_disk)
        if disk == image:
            p.error("Use a separate QCOW2 project disk")
        command += ["-drive", f"file={disk},format=qcow2,if=virtio"]
    if not opts.launch:
        print(json.dumps({"command": command, "iso_sha256_expected": PINNED,
                          "host_gpu": False, "verified": False}, indent=2))
        return
    with open(image, "rb") as stream:
        digest = file_digest(stream, "sha256").hexdigest()
    if digest != PINNED:
        p.error("ISO checksum does not match the pinned Merlin release")
    if not Path(command[0]).is_file():
        p.error("Install qemu-system-x86_64 on the launch host")
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
