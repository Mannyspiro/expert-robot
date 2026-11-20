"""Run an explicit catalogue search from a JSON file or stdin, without dispatch."""
import argparse
import json
from pathlib import Path
import sys

from merlin.scientific_loop import decompose_by_analogy, enumerate_combination_report


def _groups(values, sizes):
    if not isinstance(values, list):
        raise ValueError("expected a list of ID groups")
    result = set()
    for names in values:
        if (not isinstance(names, list) or len(names) not in sizes
                or any(not isinstance(name, str) or not name.strip() for name in names)
                or len(set(names)) != len(names)):
            raise ValueError("group requires distinct primitive IDs")
        result.add(frozenset(names))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalogue", help="JSON path, or '-' for stdin")
    parser.add_argument("--work-budget", type=int, required=True, help="Maximum pair/triple visits")
    parser.add_argument("--limit", type=int, default=64, help="Maximum number of ranked results")
    parser.add_argument("--gaps-only", action="store_true", help="Filter combinations recorded in the supplied ledger")
    args = parser.parse_args()
    try:
        if args.catalogue == "-":
            raw = sys.stdin.buffer.read(1024 * 1024 + 1)
        else:
            with Path(args.catalogue).open("rb") as stream:
                raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("catalogue JSON exceeds one MiB")
        payload = json.loads(raw)
        ledger = _groups(payload["observed_groups"], (2, 3)) if "observed_groups" in payload else None
        report = enumerate_combination_report(payload["primitives"], _groups(payload["compatible_pairs"], (2,)),
            trigger=payload["trigger"], problem=payload["problem"], max_size=payload.get("max_size", 3),
            max_cost=payload.get("max_cost", float("inf")), limit=args.limit, work_budget=args.work_budget,
            observed_groups=ledger, ledger_ref=payload.get("ledger_ref"), gaps_only=args.gaps_only)
        if "analogy" in payload:
            report["analogy"] = decompose_by_analogy(problem=payload["problem"], **payload["analogy"])
    except (ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
