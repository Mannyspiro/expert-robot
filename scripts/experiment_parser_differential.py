"""Offline bounded differential experiment; no networking or external tools."""
import argparse
import hashlib
import itertools
import json
import os
import re
from urllib.parse import unquote, urlsplit

SEGMENT = re.compile(r"[A-Za-z0-9_-]+\Z")
TOKENS = ("public", "private", "publicity", "x", ".", "..", "%70ublic", "%2e%2e", "%252e%252e", "%2f", "", "x\\y")


def router(raw):
    """Toy consumer: split URL, decode once, then remove dot segments."""
    stack = []
    for part in unquote(urlsplit(raw).path).split("/"):
        if part == "..":
            if stack:
                stack.pop()
        elif part not in ("", "."):
            stack.append(part)
    return "/" + "/".join(stack)


def permitted(path):
    return path == "/" or path.split("/")[1] == "public"


def naive_policy(raw):
    return raw.startswith("/public") or raw == "/"


def canonical(raw):
    if not isinstance(raw, str) or not 1 <= len(raw) <= 256:
        raise ValueError("length/type")
    if not raw.startswith("/") or raw.startswith("//") or not raw.isascii():
        raise ValueError("absolute ASCII path required")
    if any(c in raw for c in "?#\\") or any(ord(c) < 32 or ord(c) == 127 for c in raw):
        raise ValueError("unsupported URL syntax")
    # unquote itself tolerates malformed escapes, so validate them first.
    if re.search(r"%(?![0-9A-Fa-f]{2})", raw):
        raise ValueError("malformed escape")
    decoded = unquote(raw, encoding="ascii", errors="strict")
    if decoded == "/":
        return decoded
    segments = decoded[1:].split("/")
    # Require each original segment to decode to exactly one allowed segment.
    if len(raw[1:].split("/")) != len(segments) or not all(SEGMENT.fullmatch(s) for s in segments):
        raise ValueError("ambiguous or unsupported segment")
    return decoded


def oracle(raw):
    """Independent byte scanner and language recognizer."""
    if type(raw) is not str or not 1 <= len(raw) <= 256 or not raw.isascii() or raw[0] != "/":
        return None
    pieces = raw[1:].split("/")
    if pieces == [""]:
        return "/"
    output = []
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    for piece in pieces:
        decoded, i = "", 0
        while i < len(piece):
            c = piece[i]
            if c == "%":
                if i + 2 >= len(piece) or any(h not in "0123456789abcdefABCDEF" for h in piece[i+1:i+3]):
                    return None
                c = chr(int(piece[i+1:i+3], 16))
                i += 3
            else:
                i += 1
            if c not in allowed:
                return None
            decoded += c
        if not decoded:
            return None
        output.append(decoded)
    return "/" + "/".join(output)


def corpus():
    values = {"/", "", "//public", "/%", "/%GG", "/%ff", "/public\n", "/public\x00", "/públic", "/" + "x" * 256}
    for n in range(1, 4):
        for parts in itertools.product(TOKENS, repeat=n):
            for suffix in ("", "?q=1", "#fragment"):
                values.add("/" + "/".join(parts) + suffix)
    return sorted(values)


def mismatch(raw):
    try:
        return naive_policy(raw) and not permitted(router(raw))
    except ValueError:
        return False


def minimize(raw):
    """Deterministic deletion minimization; guarantees only 1-minimality."""
    while True:
        for i in range(len(raw)):
            candidate = raw[:i] + raw[i+1:]
            if mismatch(candidate):
                raw = candidate
                break
        else:
            return raw


def contract_violations(inputs, normalizer=canonical, policy=permitted, consumer=router):
    failures = []
    for raw in inputs:
        expected = oracle(raw)
        try:
            normalized = normalizer(raw)
        except (ValueError, UnicodeError):
            if expected is not None:
                failures.append(raw)
            continue
        try:
            good = (normalized == expected and normalizer(normalized) == normalized
                    and consumer(normalized) == normalized
                    and (not policy(normalized) or permitted(consumer(normalized))))
        except (ValueError, IndexError):
            good = False
        if not good:
            failures.append(raw)
    return failures


def run():
    inputs = corpus()
    witnesses = []
    accepted = rejected = 0
    for raw in inputs:
        if mismatch(raw):
            small = minimize(raw)
            assert mismatch(small)
            assert all(not mismatch(small[:i] + small[i+1:]) for i in range(len(small)))
            witnesses.append({"raw": raw, "consumed": router(raw), "minimized": small, "minimized_consumed": router(small)})
        expected = oracle(raw)
        try:
            normalized = canonical(raw)
        except (ValueError, UnicodeError):
            rejected += 1
            continue
        accepted += 1
    violations = len(contract_violations(inputs))
    assert witnesses and accepted and rejected and violations == 0
    mutation_counts = {
        "identity_normalizer": len(contract_violations(inputs, normalizer=lambda x: x)),
        "raw_prefix_policy": len(contract_violations(inputs, policy=naive_policy)),
        "consumer_resource_rewrite": len(contract_violations(inputs, consumer=lambda x: "/private" if x == "/public" else router(x))),
    }
    assert all(mutation_counts.values())
    return {"schema_version": 1, "experiment": "parser-differential-v1", "source_head": os.getenv("RESEARCH_HEAD_SHA", "local-unpinned"), "run_id": os.getenv("GITHUB_RUN_ID"), "input_count": len(inputs), "corpus_sha256": hashlib.sha256(json.dumps(inputs, separators=(",", ":")).encode()).hexdigest(), "tokens": list(TOKENS), "segment_depth": [1, 3], "suffixes": ["", "?q=1", "#fragment"], "original_mismatches": len(witnesses), "accepted": accepted, "rejected": rejected, "repair_violations": violations, "mutation_failure_counts": mutation_counts, "counterexamples": witnesses, "inputs": inputs, "constraints": ["N(N(x))=N(x)", "R(N(x))=N(x)", "O(x)=N(x)", "permit(x)=>permitted(R(N(x)))"], "cace_executed": False, "formal_qualified": False, "authority_expanded": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", required=True)
    args = parser.parse_args()
    report = run()
    with open(args.o, "w") as output:
        json.dump(report, output, indent=2)
        output.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("inputs", "counterexamples", "tokens", "fixed_cases")}))
