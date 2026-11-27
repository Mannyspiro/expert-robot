"""Merlin AI OS dashboard and local voice service."""
from argparse import ArgumentParser
from base64 import b64decode,b64encode
import binascii
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from threading import Lock,Thread
from time import monotonic,sleep
from urllib.request import build_opener,ProxyHandler,Request

from physics import WORLDS,solve
from tuner import configuration,tune
from host_profile import detect
from accordion import Store as AccordionStore
from research import cycle,network,workers

ROOT=Path(__file__).resolve().parent
OPENER=build_opener(ProxyHandler({}))


class Studio:
    def __init__(self,port):
        self.url=f"http://127.0.0.1:{port}"
        self.session=None
        self.lock=Lock()

    def request(self,path,body=None):
        headers={}
        value=None
        if body is not None:
            value=json.dumps(body).encode()
            headers={"Content-Type":"application/json","X-Merlin-Token":self.session}
        with OPENER.open(Request(self.url+path,value,headers),timeout=5) as response:
            return json.load(response)

    def health(self):
        try:
            return self.request("/api/health").get("ready",False)
        except OSError:
            return False

    def chat(self,text,conversation):
        with self.lock:
            if self.session is None:
                self.session=self.request("/api/status")["session_token"]
            if not conversation:
                conversation=self.request("/api/conversations",{"title":"Merlin AI OS voice session"})["conversation"]["id"]
            run=self.request("/api/chat",{"conversation_id":conversation,"message":text})["run_id"]
            until=monotonic()+115
            while monotonic()<until:
                record=self.request("/api/runs/"+run)
                state=record["run"]["status"]
                if state=="completed":
                    return next(x["content"] for x in reversed(record["conversation"]["messages"])
                                if x["role"]=="assistant"),conversation
                if state not in ("queued","running"):
                    raise RuntimeError(f"Merlin run ended with status {state}")
                sleep(.2)
        raise TimeoutError("The local model exceeded its run budget")


def mounts(args,host,research_run):
    pack=ROOT/"Merlin_Voice"
    ready=pack.is_dir()
    studio=Studio(args.studio_port)
    cace=ROOT/"CACE"
    profile=args.state/"kernel_tuning.json"
    assets={"replicator-station.scad":ROOT/"research/Matter_Replicator.scad",
            "Replicator_Voxels.scad":ROOT/"research/Replicator_Voxels.scad",
            "thermal-animation.blend":ROOT/"animation/Merlin_Thermal_Animation.blend",
            "accordion-study.json":ROOT/"Accordion_Study.json",
            "heat-history.macc":ROOT/"Heat_History.macc",
            "tensor.glb":args.portable/"3d-models/Tensor_Cells.glb",
            "floorplan.scad":args.portable/"3d-models/Merlin_Optimized_GPU_Placement.scad",
            "system.blend":args.portable/"3d-models/Merlin_Best_Configuration.blend",
            "draft.html":args.portable/"lab/Draft_By_Hand.html",
            "draft.svg":args.portable/"lab/Example_Output/Drafting_Sheet.svg",
            "wire.csv":args.portable/"lab/Example_Output/Wire_Schedule.csv",
            "proof.lean":args.portable/"formal/Chip_Arithmetic.lean"}
    holder={}
    archive_lock=Lock()
    voice_lock=Lock()

    def load_voice():
        with voice_lock:
            if "voice" not in holder:
                if not ready:
                    raise ValueError("Build the image with the Merlin Voice add-on")
                from speech import Voice
                runtime=Path(os.environ["MERLIN_RUNTIME_DIR"])
                executables=runtime/"voice-bin"
                executables.mkdir(exist_ok=True)
                node=executables/"node"
                if not node.exists():
                    from shutil import copyfile
                    copyfile(pack/"bin/node",node)
                    node.chmod(0o700)
                holder["voice"]=Voice(pack,executables,args.state/"dependencies")
        return holder["voice"]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):
            pass

        def send_data(self,value,status=200,kind="application/json"):
            body=value if isinstance(value,bytes) else json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type",kind)
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Content-Security-Policy","default-src 'self'; img-src 'self' data:; media-src 'self' blob:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; object-src 'none'; frame-ancestors 'none'")
            self.send_header("Content-Length",str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (ConnectionError,BrokenPipeError):
                pass

        def local(self,mutation=False):
            port=self.server.server_port
            allowed={f"127.0.0.1:{port}",f"localhost:{port}"}
            if self.headers.get("Host") not in allowed:
                return False
            origin=self.headers.get("Origin")
            if origin is not None and origin not in {f"http://{x}" for x in allowed}:
                return False
            return not (mutation and self.headers.get("Sec-Fetch-Site")=="cross-site")

        def do_GET(self):
            if not self.local():
                return self.send_data({"error":"Local origin only"},403)
            if self.path=="/":
                return self.send_data((ROOT/"web/index.html").read_bytes(),kind="text/html; charset=utf-8")
            static={"/shell.css":("shell.css","text/css; charset=utf-8"),
                    "/brand.js":("brand.js","text/javascript; charset=utf-8"),
                    "/wallpaper.jpg":("wallpaper.jpg","image/jpeg")}
            if self.path in static:
                name,mime=static[self.path]
                return self.send_data((ROOT/"web"/name).read_bytes(),kind=mime)
            if self.path=="/api/health":
                return self.send_data({"studio_ready":studio.health(),"voice_pack":ready,
                    "cace_pack":cace.is_dir(),"studio_port":args.studio_port,"worlds":list(WORLDS)})
            if self.path=="/api/wifi":
                return self.send_data(network.wifi())
            if self.path=="/api/xenomaths":
                return self.send_data(cycle.read(args.state))
            if self.path=="/api/workers":
                return self.send_data({"tools":workers.list_tools(args.state),"specialties":list(workers.TOOLS)})
            if self.path.startswith("/assets/worker/"):
                import re
                name=self.path.rsplit("/",1)[-1]
                if re.fullmatch(r"[a-z][a-z0-9-]{2,58}",name):
                    artifact=args.state/"xenomaths"/"workers"/name/"tool.py"
                    if artifact.is_file():
                        return self.send_data(artifact.read_bytes(),kind="text/plain; charset=utf-8")
            if self.path=="/api/hardware":
                return self.send_data(host)
            if self.path=="/api/tuning":
                return self.send_data(json.loads(profile.read_text()) if profile.exists() else {"status":"pending"})
            if self.path.startswith("/api/memory/frame/"):
                try:
                    frame=int(self.path.rsplit("/",1)[-1])
                    with archive_lock:
                        if "archive" not in holder:
                            holder["archive"]=AccordionStore(ROOT/"Heat_History.macc",host["memory_cache_bytes"])
                        store=holder["archive"]
                        shape=store.shape
                        before=(store.payload_read,store.decoded,store.misses,store.hits)
                        values=store.read((frame,0,0),(frame+1,shape[1],shape[2]))
                        result={"frame":frame,"values":values[0].tolist(),"archive_shape":shape,
                                "payload_bytes_read":store.payload_read-before[0],
                                "decoded_bytes":store.decoded-before[1],
                                "chunks":store.misses-before[2],"cache_hits":store.hits-before[3]}
                    return self.send_data(result)
                except (ValueError,KeyError,OSError):
                    return self.send_data({"error":"Invalid frame or unavailable archive"},400)
            if self.path.startswith("/api/physics/"):
                key=self.path.rsplit("/",1)[-1]
                if key in WORLDS:
                    return self.send_data(solve(key,backend=cycle.active(args.state,host["fingerprint"])))
            if self.path.startswith("/assets/"):
                name=self.path.rsplit("/",1)[-1]
                if name in ("Merlin_Chip_Candidate.scad","Metamaterial_Coupon.scad"):
                    artifact=args.state/"xenomaths"/name
                    if artifact.is_file():
                        return self.send_data(artifact.read_bytes(),kind="application/octet-stream")
                if name in assets:
                    import mimetypes
                    return self.send_data(assets[name].read_bytes(),kind=mimetypes.guess_type(name)[0] or "application/octet-stream")
            self.send_data({"error":"No such route"},404)

        def do_POST(self):
            if not self.local(True):
                return self.send_data({"error":"Local origin only"},403)
            if self.path not in ("/api/turn","/api/cace","/api/source","/api/xenomaths","/api/dependencies","/api/workers"):
                return self.send_data({"error":"No such route"},404)
            try:
                size=int(self.headers.get("Content-Length","0"))
                if not 0<size<=1320000 or self.headers.get_content_type()!="application/json":
                    raise ValueError("Unsupported request size or type")
                values=json.loads(self.rfile.read(size))
                if self.path=="/api/xenomaths":
                    Thread(target=research_run,daemon=True).start()
                    return self.send_data({"status":"queued"},202)
                if self.path=="/api/workers":
                    evidence=cycle.read(args.state)
                    if evidence.get("status")!="complete":
                        raise ValueError("Run a research cycle to produce verification data")
                    specialty,name=values.get("specialty"),values.get("name")
                    if not isinstance(specialty,str) or not isinstance(name,str):raise ValueError("Worker fields must be text")
                    return self.send_data(workers.create(args.state,specialty,name,evidence),201)
                if self.path=="/api/dependencies":
                    cache=args.state/"dependencies/narration"
                    bundled=pack/"narration/assets/model-q8.onnx"
                    if bundled.is_file():
                        return self.send_data({"voice_model":"already bundled"})
                    network.download_asset("voice-model",cache)
                    return self.send_data({"voice_model":"download verified"})
                if self.path=="/api/source":
                    url=values.get("url","")
                    if not isinstance(url,str) or len(url)>1800:
                        raise ValueError("Enter a public HTTPS page URL")
                    studio_code=args.portable/"portable"/"merlin_studio"
                    if str(studio_code) not in sys.path:
                        sys.path.insert(0,str(studio_code))
                    from public_web import fetch_public
                    record=fetch_public(url,max_bytes=524288,timeout=12,max_redirects=3)
                    report={k:record[k] for k in ("final_url","status","sha256","network_bytes")}
                    report["excerpt"]=record["text"][:1600]
                    return self.send_data(report)
                if self.path=="/api/cace":
                    if not cace.is_dir():
                        raise ValueError("Build the image with the CACE source add-on")
                    result=subprocess.run([sys.executable,"-B","-m","cace_studio.cli","run",
                        str(cace/"examples/verified_quadratic.cace")],cwd=cace,text=True,capture_output=True,timeout=60,check=True)
                    return self.send_data(json.loads(result.stdout))
                voice=None
                if "pcm" in values:
                    voice=load_voice()
                    text=voice.transcribe(b64decode(values["pcm"],validate=True))
                else:
                    text=values.get("text","")
                if not isinstance(text,str) or not text.strip() or len(text)>2200:
                    raise ValueError("Enter text or speak clearly into the microphone")
                cid=values.get("conversation")
                if cid is not None and (not isinstance(cid,str) or
                        len(cid)!=32 or any(x not in "0123456789abcdef" for x in cid)):
                    raise ValueError("Invalid local conversation")
                reply,cid=studio.chat(text.strip(),cid)
                spoken=load_voice().say(reply) if ready and values.get("speak",True) else b""
                self.send_data({"input":text,"reply":reply,"conversation":cid,
                                "wav":b64encode(spoken).decode()})
            except (ValueError,TypeError,binascii.Error) as exc:
                self.send_data({"error":str(exc)},400)
            except Exception as exc:
                print(type(exc).__name__,str(exc),file=sys.stderr,flush=True)
                self.send_data({"error":"The local workflow failed. Check the service log."},503)

    return Handler


def main():
    p=ArgumentParser(description=__doc__)
    p.add_argument("--portable",type=Path,required=True)
    p.add_argument("--state",type=Path,required=True)
    p.add_argument("--port",type=int,default=8770)
    p.add_argument("--studio-port",type=int,default=8771)
    args=p.parse_args()
    profile=args.state/"kernel_tuning.json"
    host=detect()
    chosen,fresh=configuration(profile,args.portable,host)
    os.environ.setdefault("MERLIN_BLAS_THREADS",str(host["blas_threads"]))
    studio=subprocess.Popen(["bash",str(args.portable/"START.sh"),"--state",str(args.state/"studio"),
                             "--port",str(args.studio_port),"--threads",str(chosen)])
    def benchmark():
        try:
            tune(args.portable,Path(os.environ["MERLIN_RUNTIME_DIR"]),profile,chosen,host)
        except Exception as exc:
            print("Tuner:",exc,file=sys.stderr,flush=True)
    if not fresh and os.environ.get("MERLIN_DISABLE_TUNER")!="1":
        Thread(target=benchmark,daemon=True).start()
    researcher=Studio(args.studio_port)
    def research_run():
        try:
            def interpret(text):
                if not researcher.health():raise RuntimeError("Studio not ready")
                return researcher.chat(text,None)[0]
            def retrieve(url):
                studio_code=args.portable/"portable"/"merlin_studio"
                if str(studio_code) not in sys.path:sys.path.insert(0,str(studio_code))
                from public_web import fetch_public
                return fetch_public(url,max_bytes=524288,timeout=9,max_redirects=2)
            cycle.run(args.state,args.portable,host["fingerprint"],interpret,retrieve)
        except Exception as exc:
            print("Xenomaths cycle:",type(exc).__name__,str(exc),file=sys.stderr,flush=True)
            saved=args.state/"xenomaths"
            saved.mkdir(parents=True,exist_ok=True)
            cycle.write_json(saved/"Last_Error.json",{"type":type(exc).__name__,"message":str(exc)})
    def recurring():
        from datetime import datetime,timezone
        sleep(12)
        while True:
            last=cycle.read(args.state)
            try:
                elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(last["finished"])).total_seconds()
            except (KeyError,ValueError,TypeError):elapsed=86400
            if (elapsed>=86400 or last.get("host")!=host["fingerprint"]
                    or last.get("version")!=cycle.VERSION):
                research_run()
            sleep(900)
    if os.environ.get("MERLIN_DISABLE_RESEARCH_LOOP")!="1":
        Thread(target=recurring,daemon=True).start()
    server=ThreadingHTTPServer(("127.0.0.1",args.port),mounts(args,host,research_run))
    def finish(*_):
        Thread(target=server.shutdown,daemon=True).start()
    for sig in (signal.SIGINT,signal.SIGTERM):
        signal.signal(sig,finish)
    print(f"Merlin AI OS at http://127.0.0.1:{server.server_port}/",flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        studio.terminate()
        try:
            studio.wait(timeout=15)
        except subprocess.TimeoutExpired:
            studio.kill()
            studio.wait()


if __name__=="__main__":
    main()
