#!/usr/bin/env python3
"""Build a proposal-generation view that excludes evaluation identities and infrastructure."""

import argparse
import json
import re
import shutil
from pathlib import Path

IDENT = r"(?:[A-Za-z_][A-Za-z0-9_']*|«[^»]+»)(?:\.(?:[A-Za-z_][A-Za-z0-9_']*|«[^»]+»))*"
MODIFIERS = r"(?:private|protected|noncomputable|unsafe|partial|nonrec)"
PREFIX = rf"(?:@\[[^\]]*\]\s*)*(?:{MODIFIERS}\s+)*"
DECLARATIONS = r"(?:theorem|lemma|def|abbrev|instance|structure|inductive|class|opaque|axiom|constant)"
DECL = re.compile(rf"^(?P<indent>[ \t]*){PREFIX}{DECLARATIONS}\s+(?P<name>{IDENT})(?=\s|:|\(|\{{|\[|$)")
DECL_WITHOUT_NAME = re.compile(rf"^[ \t]*{PREFIX}{DECLARATIONS}\s*$")
WRAPPER_START = re.compile(r"^[ \t]*(?:set_option|open)\b")
WRAPPER_LINE = re.compile(r"^\s*(?:set_option|open)\b.+\bin\s*$")
COMMAND = re.compile(
    rf"^(?P<indent>[ \t]*){PREFIX}(?:{DECLARATIONS}|namespace|section|end|import|prelude|"
    r"open|export|variable|variables|universe|universes|include|omit|set_option|attribute|"
    r"local|scoped|syntax|macro|macro_rules|elab|elab_rules|notation|infixl|infixr|infix|"
    r"prefix|postfix|example|mutual|initialize|builtin_initialize)\b|^(?P<hash_indent>[ \t]*)#[A-Za-z_]"
)
PREFIX_LINE = re.compile(rf"^\s*(?:(?:@\[[^\]]*\]|{MODIFIERS})\s*)+$")
SCOPE = re.compile(rf"^\s*(?:noncomputable\s+)?(?P<command>namespace|section|mutual|end)\b(?:\s+(?P<name>{IDENT}))?")
CHAR_LITERAL = re.compile(r"'(?:[^'\\]|\\(?:u\{[0-9a-fA-F]+\}|u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|[^\r\n]))'")

def declaration_match(code, following_code):
    """Recognize a named command across keyword/name lines and command wrappers."""
    candidates=[code]
    if WRAPPER_START.match(code):
        indent=code[:len(code) - len(code.lstrip(" \t"))]
        candidates.extend(indent + code[wrapper.end():].lstrip()
                          for wrapper in re.finditer(r"\bin\b", code))
    for candidate in candidates:
        match=DECL.match(candidate)
        if not match and DECL_WITHOUT_NAME.fullmatch(candidate) and following_code:
            match=DECL.match(candidate + " " + following_code.lstrip())
        if match:
            return match
    return None

def declaration_prefix(code):
    return PREFIX_LINE.fullmatch(code) or WRAPPER_LINE.fullmatch(code)

def normalized_name(name):
    # Quoting an ordinary Lean identifier does not change the symbol it denotes.
    parts=re.findall(r"[A-Za-z_][A-Za-z0-9_']*|«[^»]+»", name)
    return ".".join(part[1:-1] if part.startswith("«") and
                    re.fullmatch(r"[A-Za-z_][A-Za-z0-9_']*", part[1:-1])
                    else part for part in parts)

def lean_code_lines(text):
    """Mask comments, strings and syntax quotations before locating commands."""
    block_depth = 0
    in_string = False
    escaped = False
    quotation_closers = []
    in_identifier = False
    for line in text.splitlines():
        code = []
        i = 0
        while i < len(line):
            pair = line[i:i + 2]
            if block_depth:
                if pair == "/-":
                    block_depth += 1
                    code.extend("  ")
                    i += 2
                elif pair == "-/":
                    block_depth -= 1
                    code.extend("  ")
                    i += 2
                else:
                    code.append(" ")
                    i += 1
            elif in_string:
                char = line[i]
                code.append(" ")
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                i += 1
            elif in_identifier:
                char = line[i]
                code.append(" " if quotation_closers else char)
                if char == "»":
                    in_identifier = False
                i += 1
            elif pair == "--":
                code.extend(" " * (len(line) - i))
                break
            elif pair == "/-":
                block_depth = 1
                code.extend("  ")
                i += 2
            elif line[i] == "«":
                in_identifier = True
                code.append(" " if quotation_closers else line[i])
                i += 1
            elif line[i] == "'" and (i == 0 or not (line[i - 1].isalnum() or line[i - 1] in "_'»")) and (literal := CHAR_LITERAL.match(line, i)):
                code.extend(" " * (literal.end() - i))
                i = literal.end()
            elif line[i] == '"':
                in_string = True
                code.append(" ")
                i += 1
            elif quotation_closers:
                char = line[i]
                code.append(" ")
                if char in "([{":
                    quotation_closers.append({"(": ")", "[": "]", "{": "}"}[char])
                elif char == quotation_closers[-1]:
                    quotation_closers.pop()
                i += 1
            elif line[i] == "`" and i + 1 < len(line) and line[i + 1] in "([":
                quotation_closers.append({"(": ")", "[": "]"}[line[i + 1]])
                code.extend("  ")
                i += 2
            else:
                code.append(line[i])
                i += 1
        yield "".join(code)

def inside(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False

def sanitize_lean(text, hidden):
    hidden_set = set(hidden)
    out=[]
    out_code=[]
    # Sections and mutual blocks preserve the namespace but each consumes `end`.
    scopes=[""]
    skipping_indent=None
    lines=text.splitlines()
    codes=list(lean_code_lines(text))
    following_codes=[""] * len(codes)
    next_code=""
    for index in range(len(codes) - 1, -1, -1):
        following_codes[index]=next_code
        if codes[index].strip():
            next_code=codes[index]
    for index, (line, code) in enumerate(zip(lines, codes)):
        match=declaration_match(code, following_codes[index])
        command=COMMAND.match(code)
        prefix=declaration_prefix(code)
        indent=len(code) - len(code.lstrip(" \t"))
        if skipping_indent is not None:
            # Named declaration commands can indent independently of their
            # predecessor; proof-local options still need indentation protection.
            if match or (indent <= skipping_indent and (command or prefix)):
                skipping_indent=None
            else:
                continue
        if match:
            name=normalized_name(match.group("name"))
            if name.startswith("_root_."):
                qualified=name[len("_root_."):]
            else:
                qualified=".".join(x for x in (scopes[-1], name) if x)
            if qualified in hidden_set or ("." not in name and name in hidden_set):
                # Attributes/modifiers on preceding lines belong to this declaration.
                last=len(out_code) - 1
                while last >= 0 and not out_code[last].strip():
                    last -= 1
                while last >= 0 and declaration_prefix(out_code[last]):
                    del out[last:]
                    del out_code[last:]
                    last -= 1
                    while last >= 0 and not out_code[last].strip():
                        last -= 1
                out.append(match.group("indent") + "-- [blind-eval declaration redacted]")
                out_code.append("")
                skipping_indent=indent
                continue
        scope=SCOPE.match(code)
        if scope:
            action=scope.group("command")
            if action == "namespace":
                name=normalized_name(scope.group("name") or "")
                if name.startswith("_root_."):
                    scopes.append(name[len("_root_."):])
                else:
                    scopes.append(".".join(x for x in (scopes[-1], name) if x))
            elif action in {"section", "mutual"}:
                scopes.append(scopes[-1])
            elif len(scopes) > 1:
                scopes.pop()
        clean=line
        for token in hidden:
            clean=clean.replace(token,"[REDACTED_EVAL_SYMBOL]")
        out.append(clean)
        out_code.append(code)
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
