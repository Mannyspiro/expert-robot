#!/usr/bin/env python3
"""Build a pinned, self-verifying Termux-compatible Merlin Studio source ZIP."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("merlin_portable_builder", ROOT / "portable" / "build_portable.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
extra = {
    "START_ANDROID.sh": "portable/android_termux/START_ANDROID.sh",
    "INSTALL_ANDROID_MODEL.sh": "portable/android_termux/INSTALL_ANDROID_MODEL.sh",
    "README_ANDROID.md": "portable/android_termux/README_ANDROID.md",
}
output = ROOT / "dist" / "Merlin-Studio-Android-Termux.zip"
payload, origins = module.collect_sources()
for dest, origin in extra.items():
    payload[dest] = module.source_bytes(origin)
    origins[dest] = origin
manifest = {
    "schema": "merlin-studio-portable/1",
    "version": "0.2.0-android-termux",
    "archive_root": "Merlin_Studio",
    "platform_profile": "android-termux-source",
    "python_requirement": ">=3.10; separately installed in Termux",
    "native_protocol": {"included": False, "scope": "protocol_source_only", "platform": None},
    "contains_model_weights": False,
    "contains_python_runtime": False,
    "contains_inference_engine": False,
    "contains_user_state": False,
    "contains_credentials": False,
    "device_tested": False,
    "zip_timestamp": "1980-01-01T00:00:00",
    "files": [],
    "integrity_scope": "All ZIP members are hashed; installation, Android compatibility, license, and model quality are not independently certified.",
}
for name, data in sorted(payload.items()):
    assert len(data) <= 64 * 1024 * 1024 and name != "PACKAGE_MANIFEST.json"
    executable = name in module.EXECUTABLES or name in ("START_ANDROID.sh", "INSTALL_ANDROID_MODEL.sh")
    manifest["files"].append({
        "path": name, "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "mode": "0755" if executable else "0644",
        "source": origins[name],
    })
payload["PACKAGE_MANIFEST.json"] = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
output.parent.mkdir(parents=True, exist_ok=True)
with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".zip", delete=False) as tmp:
    temp = Path(tmp.name)
try:
    with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(payload.items()):
            info = zipfile.ZipInfo("Merlin_Studio/" + name, module.ZIP_TIME)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | (0o755 if name in module.EXECUTABLES or name in ("START_ANDROID.sh","INSTALL_ANDROID_MODEL.sh") else 0o644)) << 16
            archive.writestr(info, data)
    os.replace(temp, output)
finally:
    temp.unlink(missing_ok=True)
print(json.dumps({"output": str(output), "bytes": output.stat().st_size, "files": len(payload), "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}, sort_keys=True))
