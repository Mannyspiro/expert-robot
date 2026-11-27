"""Local Wi-Fi visibility and verified optional model recovery."""
from hashlib import file_digest,sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parent
MANIFEST=json.loads((ROOT/"Sources.json").read_text())


def wifi():
    try:
        tool=subprocess.run(["nmcli","-t","-f","TYPE,STATE","device","status"],
                             capture_output=True,text=True,timeout=3,check=True)
        devices=[row.split(":",1)[1] for row in tool.stdout.splitlines() if row.startswith("wifi:")]
        return {"network_manager":True,"wifi_states":devices,"wifi_connected":"connected" in devices,
                "help":'Use the desktop Network menu or nmcli --ask device wifi connect "YOUR_SSID"'}
    except (OSError,subprocess.SubprocessError):
        return {"network_manager":False,"wifi_states":[],"wifi_connected":False,
                "help":"Use the operating system network settings. NetworkManager was not visible to Merlin."}


def checksum(file):
    with file.open("rb") as f:return file_digest(f,"sha256").hexdigest()


def download_asset(name,cache,get=urlopen):
    spec=MANIFEST["assets"][name]
    path=Path(cache)/spec["filename"]
    if path.is_file() and checksum(path)==spec["sha256"]:return path
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent,prefix=".download-",delete=False) as out:
        staging=Path(out.name)
        try:
            received=0
            digest=sha256()
            deadline=time.monotonic()+180
            with get(Request(spec["url"],headers={"Accept-Encoding":"identity"}),timeout=12) as r:
                if not r.geturl().startswith("https://"):raise ValueError("Download must use HTTPS")
                while block:=r.read(1024**2):
                    received+=len(block)
                    if received>spec["bytes"] or time.monotonic()>deadline:raise ValueError("Download budget exceeded")
                    digest.update(block);out.write(block)
            if received!=spec["bytes"] or digest.hexdigest()!=spec["sha256"]:
                raise ValueError("Asset size or SHA-256 mismatch")
            out.flush();os.fsync(out.fileno())
            staging.replace(path)
        finally:
            staging.unlink(missing_ok=True)
    return path
