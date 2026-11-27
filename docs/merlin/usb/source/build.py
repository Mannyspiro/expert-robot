"""Remaster a verified Debian amd64 live ISO into a Meridian Merlin AI OS image."""
from argparse import ArgumentParser
from hashlib import file_digest
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
from urllib.request import urlopen
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
MODEL_SHA256 = "7671c0c304e6ce5a7fc577bcb12aba01e2c155cc2efd29b2213c95b18edaf6ed"
UNIT = """[Unit]
Description=Merlin AI OS
After=local-fs.target
ConditionPathExists=/run/live/medium/merlin/START_OS.sh

[Service]
Type=simple
DynamicUser=yes
CacheDirectory=merlin-ai-os
StateDirectory=merlin-ai-os
Environment=MERLIN_CACHE_DIR=/var/cache/merlin-ai-os MERLIN_OS_STATE=/var/lib/merlin-ai-os
ExecStart=/bin/bash /run/live/medium/merlin/START_OS.sh
Restart=on-failure
RestartSec=6
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
"""

AUTOSTART = """[Desktop Entry]
Type=Application
Name=Merlin AI OS
Exec=/bin/bash /usr/local/bin/open-merlin-ai-os
Terminal=false
"""


def digest(path):
    with path.open("rb") as f:
        return file_digest(f, "sha256").hexdigest()


def run(command, capture=False, check=True):
    return subprocess.run(command, check=check, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.STDOUT if capture else None)


def unpack(path, target, name):
    with ZipFile(path) as z:
        for entry in z.infolist():
            relative = PurePosixPath(entry.filename)
            if not relative.parts or relative.parts[0] != name or ".." in relative.parts or "\\" in entry.filename:
                raise ValueError(f"Unexpected path in {name} archive")
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Archive contains a symbolic link")
        z.extractall(target)
    return target/name


def verify_iso(xorriso,path):
    process=run([xorriso,"-indev",str(path),"-report_el_torito","plain","-report_system_area","plain"],True)
    report=process.stdout
    if not (re.search(r'El Torito boot img\s*:\s*\d+\s+UEFI\s+y',report)
            and re.search(r'El Torito boot img\s*:\s*\d+\s+BIOS\s+y',report)
            and re.search(r'System area summary:.*(?:GPT|isohybrid)',report)):
        raise ValueError("The ISO must contain hybrid USB boot metadata and bootable UEFI and BIOS entries")
    return report


def write_overlay(root):
    system_unit=root/"etc/systemd/system/merlin-live.service"
    system_unit.parent.mkdir(parents=True)
    system_unit.write_text(UNIT)
    wants=root/"etc/systemd/system/multi-user.target.wants"
    wants.mkdir()
    (wants/"merlin-live.service").symlink_to("../merlin-live.service")
    login=root/"etc/xdg/autostart/merlin-ai-os.desktop"
    login.parent.mkdir(parents=True)
    login.write_text(AUTOSTART)
    browse=root/"usr/share/applications/merlin-internet.desktop"
    browse.parent.mkdir(parents=True)
    browse.write_text("[Desktop Entry]\nType=Application\nName=Internet Browser\n"
                      "Exec=xdg-open https://www.debian.org/\nIcon=web-browser\nCategories=Network;\n")
    opener=root/"usr/local/bin/open-merlin-ai-os"
    opener.parent.mkdir(parents=True)
    opener.write_text("""#!/bin/bash
for i in {1..150}; do
  if (exec 3<>/dev/tcp/127.0.0.1/8770) 2>/dev/null; then
    exec xdg-open http://127.0.0.1:8770/
  fi
  sleep 1
done
""")
    opener.chmod(0o755)


def modules_for(xorriso,base,out):
    args=[xorriso,"-osirrox","on","-indev",str(base)]
    inquiry=run(args+["-ls","/live","--"],True)
    probe=run(args+["-extract","/live/filesystem.module",str(out)],True,False)
    if probe.returncode==0 and out.exists():
        modules=[s.strip() for s in out.read_text().splitlines()
                 if s.strip() and not s.lstrip().startswith("#")]
    elif re.search(r"(?m)^'?filesystem\.squashfs'?$",inquiry.stdout.strip()):
        modules=["filesystem.squashfs"]
    else:
        raise ValueError("Cannot identify the live filesystem order under /live")
    if not modules or any(not re.fullmatch(r"[A-Za-z0-9_.-]+\.squashfs",x) for x in modules):
        raise ValueError("Unrecognized Debian filesystem.module")
    if "merlin.squashfs" in modules or "merlin.squashfs" in inquiry.stdout:
        raise ValueError("Start with the pristine live base ISO")
    out.write_text("\n".join([*modules,"merlin.squashfs"])+"\n")


def build(args):
    output=args.output.resolve()
    if output.exists() or output.suffix.lower()!=".iso" or str(output).startswith("/dev/"):
        raise ValueError("Choose a new regular .iso output path")
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".merlin-build-",dir=output.parent) as staging:
        work=Path(staging)
        base=args.base.resolve() if args.base else work/"debian-live.iso"
        if args.download:
            for source in args.download:
                if not source.startswith("https://"):
                    raise ValueError("Use an HTTPS Debian Live mirror URL")
                print(f"Downloading the selected live base from {source}",flush=True)
                try:
                    with urlopen(source,timeout=80) as src,base.open("wb") as dst:
                        shutil.copyfileobj(src,dst,1024**2)
                    if digest(base)!=args.sha256.lower():
                        raise ValueError("Downloaded base SHA-256 mismatch")
                    break
                except (OSError,ValueError) as exc:
                    base.unlink(missing_ok=True)
                    print(f"Download unavailable: {exc}",flush=True)
            else:
                raise ValueError("No mirror returned the verified Debian live image")
        print("Verifying base and previous Merlin USB archive",flush=True)
        if digest(base)!=args.sha256.lower():
            raise ValueError("Debian live ISO SHA-256 mismatch")
        verify_iso(args.xorriso,base)
        modules=work/"filesystem.module"
        modules_for(args.xorriso,base,modules)
        payload=work/"merlin"
        shutil.copytree(HERE/"payload",payload,ignore=shutil.ignore_patterns("__pycache__","CACE","Merlin_Voice","Merlin_Chip_USB"))
        portable=unpack(args.merlin,payload,"Merlin_Chip_USB")
        if digest(portable/"model/qwen2.5-0.5b-instruct-q4_0.gguf")!=MODEL_SHA256:
            raise ValueError("Merlin checkpoint SHA-256 mismatch")
        if args.voice:
            unpack(args.voice,payload,"Merlin_Voice")
        if args.cace:
            unpack(args.cace,payload,"CACE")
        root=work/"overlay"
        write_overlay(root)
        layer=work/"merlin.squashfs"
        run([args.mksquashfs,str(root),str(layer),"-noappend","-all-root",
             "-comp","gzip","-no-progress","-processors","2"])
        candidate=work/"result.iso"
        run([args.xorriso,"-indev",str(base),"-outdev",str(candidate),
             "-map",str(payload),"/merlin","-map",str(layer),"/live/merlin.squashfs",
             "-map",str(modules),"/live/filesystem.module","-boot_image","any","replay"])
        report=verify_iso(args.xorriso,candidate)
        data={"sha256":digest(candidate),"base_sha256":args.sha256.lower(),"boot_metadata":report,
              "boot_execution":"Not tested by build.py. See the separate VM test.",
              "runtime":"x86-64 Linux","voice":bool(args.voice),"cace":bool(args.cace)}
        candidate.replace(output)
        output.with_suffix(".build.json").write_text(json.dumps(data,indent=2)+"\n")
        print(f"Created {output} with SHA-256 {data['sha256']}")


def main():
    p=ArgumentParser(description=__doc__)
    base=p.add_mutually_exclusive_group(required=True)
    base.add_argument("--base",type=Path,help="Official Debian Live amd64 ISO already downloaded")
    base.add_argument("--download",action="append",help="Pinned official Debian Live amd64 ISO HTTPS URL. Repeat for fallbacks.")
    p.add_argument("--sha256",required=True,help="Verified hash of the chosen Debian base ISO")
    p.add_argument("--merlin",type=Path,required=True,help="Prior Merlin_Chip_USB_Linux_x86_64.zip")
    p.add_argument("--voice",type=Path)
    p.add_argument("--cace",type=Path)
    p.add_argument("--output",type=Path,default=Path("Merlin_AI_OS.iso"))
    p.add_argument("--xorriso",default="xorriso")
    p.add_argument("--mksquashfs",default="mksquashfs")
    args=p.parse_args()
    if not re.fullmatch(r"[A-Fa-f0-9]{64}",args.sha256):
        p.error("--sha256 must be a SHA-256 digest")
    build(args)


if __name__=="__main__":
    main()
