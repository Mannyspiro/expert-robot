#!/usr/bin/env python3
"""Explicit real-model acceptance on an isolated Linux runner.

Requires pre-provisioned, reviewed model weights and llama-server executable.
Never downloads assets, invents licenses, runs on a public interface, or
claims model-weight provenance from a successful HTTP response alone.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time

from merlin_real_local_inference_acceptance import validate

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"portable"/"merlin_studio"))
from model import isolated_model_environment


def digest(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def checked(path:Path, expected:str)->Path:
    if not isinstance(expected,str) or len(expected)!=64 or any(c not in "0123456789abcdef" for c in expected):
        raise ValueError("explicit lowercase SHA-256 required")
    if path.is_symlink() or not path.is_file() or path.stat().st_size<=0:
        raise ValueError("real nonempty regular asset required")
    if digest(path)!=expected:
        raise ValueError("asset digest mismatch")
    return path.resolve(strict=True)


def run(server:Path, model:Path, server_sha:str, model_sha:str, *, port:int=18772, timeout:int=90)->dict:
    if not isinstance(port,int) or not 1024<=port<=65535:
        raise ValueError("invalid local port")
    if type(timeout) is not int or not 10<=timeout<=120:
        raise ValueError("invalid timeout")
    server=checked(server,server_sha)
    model=checked(model,model_sha)
    if not os.access(server,os.X_OK):
        raise ValueError("llama-server is not executable")
    command=[str(server),"--model",str(model),"--alias","local",
             "--host","127.0.0.1","--port",str(port),
             "--ctx-size","2048","--threads","2","--jinja"]
    # The runner's model is untrusted with respect to CI credentials.
    # Give it a private home rather than the CI service account's home.
    import tempfile
    with tempfile.TemporaryDirectory(prefix="merlin-model-home-") as home:
        child_env=isolated_model_environment()
        child_env["HOME"]=home
        child_env["XDG_CONFIG_HOME"]=str(Path(home)/"config")
        child_env["XDG_CACHE_HOME"]=str(Path(home)/"cache")
        child_env["TMPDIR"]=home
        child_env["TMP"]=home
        child_env["TEMP"]=home
        child_env["USERPROFILE"]=home
        child_env["APPDATA"]=str(Path(home)/"config")
        child_env["LOCALAPPDATA"]=str(Path(home)/"cache")
        return _run_isolated(command,server_sha,model_sha,port,timeout,child_env)


def _run_isolated(command,server_sha,model_sha,port,timeout,child_env):
    proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                          start_new_session=True,env=child_env)
    try:
        endpoint=f"http://127.0.0.1:{port}/v1/chat/completions"
        deadline=time.monotonic()+timeout
        last_error="server not ready"
        # Poll readiness without issuing generation requests. A model may load
        # slowly; once ready, issue exactly one measured inference challenge.
        import urllib.request
        import urllib.error
        ready=False
        while time.monotonic()<deadline:
            if proc.poll() is not None:
                raise RuntimeError("real model process exited before readiness")
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/v1/models",timeout=2
                ) as response:
                    payload=json.load(response)
                ready=any(item.get("id")=="local" for item in payload.get("data",[]))
                if ready:
                    break
            except (OSError,ValueError,KeyError,TypeError):
                pass
            time.sleep(min(1,max(0,deadline-time.monotonic())))
        if not ready:
            raise RuntimeError("real model did not advertise requested model before deadline")
        remaining=deadline-time.monotonic()
        if remaining<10:
            raise RuntimeError("insufficient remaining inference budget after model loading")
        result=validate(endpoint,"local",timeout=min(120,max(10,int(remaining))))
        result.update(server_sha256=server_sha,model_sha256=model_sha,
                      server_process_pid=proc.pid,
                      source="preprovisioned_sha256_checked_assets",
                      model_weights_file_verified=True,
                      model_process_started=True,
                      independent_weights_provenance=False,
                      generation_attempts=1)
        return result
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid,signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL)
                proc.wait(timeout=5)


def main():
    p=argparse.ArgumentParser()
    for flag in ("server","model","server-sha256","model-sha256","output"):
        p.add_argument("--"+flag,required=True)
    p.add_argument("--port",type=int,default=18772)
    args=p.parse_args()
    output=Path(args.output)
    if output.exists() or output.is_symlink():
        raise ValueError("refusing to overwrite acceptance evidence")
    result=run(Path(args.server),Path(args.model),args.server_sha256,args.model_sha256,port=args.port)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x") as f:
        json.dump(result,f,sort_keys=True,indent=2)
        f.write("\n")
    print(json.dumps({"generation_request_completed":result["generation_request_completed"],
                      "challenge_token_echoed":result["challenge_token_echoed"],
                      "model_sha256":result["model_sha256"]}))
    if not result["challenge_token_echoed"]:
        raise SystemExit("model generated response but failed challenge")


if __name__=="__main__":
    main()
