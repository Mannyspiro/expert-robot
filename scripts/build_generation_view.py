#!/usr/bin/env python3
"""Build a proposal-generation view that excludes evaluation identities and infrastructure."""

import argparse
import json
import re
import shutil
from pathlib import Path

DECL = re.compile(r"^(?:theorem|lemma|def|abbrev|instance|structure|inductive|class)\s+([A-Za-z0-9_'.]+)")

def inside(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False

def sanitize_lean(text, hidden):
    short={item.rsplit(".",1)[-1] for item in hidden if "." in item}
    lines=text.splitlines()
    out=[]
    skipping=False
    for line in lines:
        match=DECL.match(line)
        if skipping and match:
            skipping=False
        if not skipping and match and match.group(1) in short:
            out.append("-- [blind-eval declaration redacted]")
            skipping=True
            continue
        if skipping:
            continue
        clean=line
        for token in hidden:
            clean=clean.replace(token,"[REDACTED_EVAL_SYMBOL]")
        out.append(clean)
    return "\n".join(out)+"\n"

def sanitize_registry(text, hidden):
    payload=json.loads(text)
    def contaminated(value):
        rendered=json.dumps(value,ensure_ascii=False)
        return any(token in rendered for token in hidden)
    if isinstance(payload,dict) and isinstance(payload.get("theorems"),list):
        payload["theorems"]=[x for x in payload["theorems"] if not contaminated(x)]
    elif isinstance(payload,list):
        payload=[x for x in payload if not contaminated(x)]
    else:
        # Generic recursive replacement for unexpected schema.
        rendered=json.dumps(payload,ensure_ascii=False)
        for token in hidden:
            rendered=rendered.replace(token,"[REDACTED_EVAL_SYMBOL]")
        return json.dumps(json.loads(rendered),indent=2,ensure_ascii=False)+"\n"
    return json.dumps(payload,indent=2,ensure_ascii=False)+"\n"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("source",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--policy",type=Path,default=Path("config/blind_evaluation_policy.json"))
    args=p.parse_args()

    source=args.source.resolve()
    output=args.output.resolve()
    policy=json.loads(args.policy.read_text(encoding="utf-8"))
    hidden=policy["hidden_identifiers"]

    if output.exists():
        raise SystemExit("output must not already exist")
    output.mkdir(parents=True)

    copied=[]
    for rel in policy["generation_include"]:
        src=source/rel
        if not src.exists():
            continue
        paths=[src] if src.is_file() else [p for p in src.rglob("*") if p.is_file()]
        for item in paths:
            relative=item.relative_to(source)
            rels=relative.as_posix()
            if any(rels==x or rels.startswith(x) for x in policy["generation_excluded_prefixes"]):
                continue
            dest=output/relative
            dest.parent.mkdir(parents=True,exist_ok=True)
            if item.suffix in {".lean",".cpp",".hpp",".h",".cc",".cxx",".txt",".md"}:
                content=item.read_text(encoding="utf-8")
                content=sanitize_lean(content,hidden) if item.suffix==".lean" else content
                for token in hidden:
                    content=content.replace(token,"[REDACTED_EVAL_SYMBOL]")
                dest.write_text(content,encoding="utf-8")
            elif relative.as_posix()=="formal/theorem_registry.json":
                dest.write_text(sanitize_registry(item.read_text(encoding="utf-8"),hidden),encoding="utf-8")
            else:
                shutil.copyfile(item,dest)
            copied.append(rels)

    leaks=[]
    for item in output.rglob("*"):
        if not item.is_file():
            continue
        try:
            content=item.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for token in hidden:
            if token in content:
                leaks.append({"path":item.relative_to(output).as_posix(),"token":token})
    if leaks:
        raise SystemExit("blind generation view leaked evaluation identities: "+json.dumps(leaks))

    manifest={"schema_version":1,"copied_files":sorted(copied),"hidden_identifier_count":len(hidden),"leak_count":0}
    (output/"GENERATION_VIEW_MANIFEST.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(manifest,indent=2))

if __name__=="__main__":
    main()
