#!/usr/bin/env python3
"""Scan multiple prepared PinPatch roots and report duplicate or divergent pins."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, action="append", required=True, help="Repeat for each prepared root")
    parser.add_argument("--jobs", type=int, default=4, help="Concurrent scans (1-16, default: 4)")
    return parser.parse_args()


def scan_one(scanner: Path, root: Path) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, str(scanner), "--root", str(root)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        message = completed.stderr.strip() or completed.stdout.strip() or f"scanner exited {completed.returncode}"
        raise ValueError(message)
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise ValueError("scanner returned a non-object JSON value")
    return value


def main() -> int:
    args = parse_args()
    if not 1 <= args.jobs <= 16:
        print("scan_batch: --jobs must be between 1 and 16", file=sys.stderr)
        return 2
    scanner = Path(__file__).resolve().with_name("scan_pending.py")
    if not scanner.is_file():
        print(f"scan_batch: scan_pending.py not found: {scanner}", file=sys.stderr)
        return 2

    items: list[dict[str, object] | None] = [None] * len(args.root)
    with ThreadPoolExecutor(max_workers=min(args.jobs, len(args.root))) as executor:
        jobs = {executor.submit(scan_one, scanner, root): index for index, root in enumerate(args.root)}
        for future in as_completed(jobs):
            index = jobs[future]
            try:
                scan = future.result()
                items[index] = {"index": index, "root": str(args.root[index]), "status": "ready", "scan": scan}
            except Exception as error:
                items[index] = {"index": index, "root": str(args.root[index]), "status": "error", "error": str(error)}

    complete = [item for item in items if item is not None]
    occurrences: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    revisions_by_pin: dict[str, set[str]] = defaultdict(set)
    for item in complete:
        if item["status"] != "ready":
            continue
        scan = item["scan"]
        for pending in scan.get("pending", []):
            key = (pending["pinID"], pending["revisionID"])
            occurrence = {"itemIndex": item["index"], "root": item["root"]}
            occurrences[key].append(occurrence)
            revisions_by_pin[key[0]].add(key[1])

    duplicates = [
        {"pinID": key[0], "revisionID": key[1], "occurrences": values}
        for key, values in sorted(occurrences.items())
        if len(values) > 1
    ]
    conflicts = [
        {"pinID": pin_id, "revisionIDs": sorted(revisions)}
        for pin_id, revisions in sorted(revisions_by_pin.items())
        if len(revisions) > 1
    ]
    error_count = sum(item["status"] == "error" for item in complete)
    print(json.dumps({
        "rootCount": len(args.root),
        "readyCount": len(complete) - error_count,
        "errorCount": error_count,
        "uniquePendingCount": len(occurrences),
        "duplicates": duplicates,
        "pinConflicts": conflicts,
        "items": complete,
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
