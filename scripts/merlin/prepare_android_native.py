#!/usr/bin/env python3
"""Stage pinned llama.cpp source for Gradle NDK. No models or user data are fetched."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
SOURCE_SHA="44d50873b56b568c28ef2ad8d6445069feaa9fbd"
TARGET=ROOT/"android/merlin-apk/app/src/main/cpp/vendor/llama.cpp"

def main():
    if TARGET.exists():
        if TARGET.is_symlink() or not (TARGET/"include/llama.h").is_file():
            raise RuntimeError("Native source directory is corrupt or unsafe")
        raise RuntimeError("Refusing to overwrite existing llama.cpp checkout")
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="merlin-android-llama-") as work:
        checkout=Path(work)/"repo"
        env={"PATH":os.environ.get("PATH","/usr/bin:/bin"),
             "HOME":work,"LANG":"C.UTF-8","LC_ALL":"C.UTF-8"}
        commands=(
            ["git","clone","--quiet","--filter=blob:none","--no-checkout",
             "https://github.com/ggml-org/llama.cpp.git",str(checkout)],
            ["git","-C",str(checkout),"fetch","--quiet","--depth","1","origin",SOURCE_SHA],
            ["git","-C",str(checkout),"checkout","--quiet","--detach",SOURCE_SHA]
        )
        for cmd in commands:
            subprocess.run(cmd,env=env,check=True,timeout=240)
        actual=subprocess.check_output(
            ["git","-C",str(checkout),"rev-parse","HEAD"],env=env,text=True).strip()
        if actual!=SOURCE_SHA:raise RuntimeError("Pinned native source SHA mismatch")
        shutil.rmtree(checkout/".git")
        shutil.copytree(checkout,TARGET,symlinks=False,
                        ignore=shutil.ignore_patterns("*.gguf","tests","examples","docs","media"))
    if not (TARGET/"include/llama.h").is_file():
        raise RuntimeError("Pinned llama header absent")
    print("Pinned llama.cpp Android source:",SOURCE_SHA)

if __name__=="__main__":
    main()
