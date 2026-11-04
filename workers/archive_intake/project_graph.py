#!/usr/bin/env python3
"""Export a deterministic, provenance-aware Merlin project graph as JSON."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
from register_inventory import RegistryError, validate_manifest

def _id(kind: str, value: str) -> str:
    digest=hashlib.sha256((kind+"\0"+value).encode("utf-8")).hexdigest()
    return "urn:merlin:"+kind+":"+digest

def build_graph(manifest: dict, project_id: str, repository: str | None = None,
                commit_sha: str | None = None) -> dict:
    validate_manifest(manifest)
    if not isinstance(project_id,str) or not project_id.strip():
        raise RegistryError("project_id is required")
    if bool(repository) != bool(commit_sha):
        raise RegistryError("repository and commit_sha must be supplied together")
    if commit_sha and (len(commit_sha)!=40 or any(c not in "0123456789abcdef" for c in commit_sha.lower())):
        raise RegistryError("commit_sha must be a full 40-character hexadecimal SHA")
    project_node=_id("project",project_id)
    intake_node=_id("intake",manifest["intake_id"])
    nodes=[
      {"id":project_node,"type":"Project","project_id":project_id},
      {"id":intake_node,"type":"Intake","intake_id":manifest["intake_id"],
       "archive_sha256":manifest["archive"]["sha256"],"manifest_version":manifest["manifest_version"]}
    ]
    edges=[{"id":_id("edge",project_node+"|hasIntake|"+intake_node),
            "from":project_node,"relation":"hasIntake","to":intake_node}]
    if repository:
        source_node=_id("git-commit",repository+"@"+commit_sha.lower())
        nodes.append({"id":source_node,"type":"GitCommit","repository_full_name":repository,
                      "commit_sha":commit_sha.lower()})
        edges.append({"id":_id("edge",project_node+"|hasSource|"+source_node),
                      "from":project_node,"relation":"hasSource","to":source_node})
    for item in manifest["files"]:
        occurrence_key=manifest["intake_id"]+"|"+item["path"]
        occurrence_node=_id("occurrence",occurrence_key)
        artifact_node=_id("artifact",item["sha256"])
        nodes.append({"id":occurrence_node,"type":"ArtifactOccurrence","path":item["path"],
          "size_bytes":item["size_bytes"],"classification":item["classification"]})
        nodes.append({"id":artifact_node,"type":"Artifact","sha256":item["sha256"]})
        edges.extend([
          {"id":_id("edge",intake_node+"|contains|"+occurrence_node),
           "from":intake_node,"relation":"contains","to":occurrence_node},
          {"id":_id("edge",occurrence_node+"|hasContent|"+artifact_node),
           "from":occurrence_node,"relation":"hasContent","to":artifact_node}
        ])
    unique={node["id"]:node for node in nodes}
    return {"graph_version":"1.0","project_id":project_id,"nodes":list(unique.values()),"edges":edges}

def main():
    parser=argparse.ArgumentParser(description="Export a local Merlin provenance graph; no graph service is contacted.")
    parser.add_argument("manifest",type=Path); parser.add_argument("--project-id",required=True)
    parser.add_argument("--repository"); parser.add_argument("--commit-sha"); parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    try:
        data=json.loads(args.manifest.read_text(encoding="utf-8"))
        graph=build_graph(data,args.project_id,args.repository,args.commit_sha)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(graph,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print(json.dumps({"status":"exported","nodes":len(graph["nodes"]),"edges":len(graph["edges"]),"out":str(args.out)},indent=2))
        return 0
    except (OSError,ValueError,RegistryError) as exc:
        print(json.dumps({"status":"rejected","error":str(exc)},indent=2),file=sys.stderr); return 1
if __name__=="__main__": raise SystemExit(main())
