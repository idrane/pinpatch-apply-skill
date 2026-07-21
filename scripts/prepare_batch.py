#!/usr/bin/env python3
"""Safely prepare multiple PinPatch exports concurrently."""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from prepare_input import prepare_one


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True, help="Repeat for each input")
    parser.add_argument("--work-dir", type=Path, required=True, help="Writable temporary parent")
    parser.add_argument("--jobs", type=int, default=4, help="Concurrent preparations (1-16, default: 4)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.jobs <= 16:
        print("prepare_batch: --jobs must be between 1 and 16", file=sys.stderr)
        return 2

    items: list[dict[str, object] | None] = [None] * len(args.input)
    unique: dict[str, int] = {}
    resolved_inputs: dict[int, str] = {}
    jobs: dict[object, int] = {}

    with ThreadPoolExecutor(max_workers=min(args.jobs, len(args.input))) as executor:
        for index, source in enumerate(args.input):
            try:
                resolved = str(source.expanduser().resolve(strict=True))
            except OSError as error:
                items[index] = {"index": index, "input": str(source), "status": "error", "error": str(error)}
                continue
            resolved_inputs[index] = resolved
            if resolved in unique:
                items[index] = {
                    "index": index,
                    "input": resolved,
                    "status": "duplicate",
                    "duplicateOf": unique[resolved],
                }
                continue
            unique[resolved] = index
            future = executor.submit(prepare_one, Path(resolved), args.work_dir)
            jobs[future] = index

        for future in as_completed(jobs):
            index = jobs[future]
            try:
                prepared = future.result()
                items[index] = {"index": index, "status": "ready", **prepared}
            except Exception as error:
                items[index] = {
                    "index": index,
                    "input": resolved_inputs[index],
                    "status": "error",
                    "error": str(error),
                }

    for index, item in enumerate(items):
        if item is None or item["status"] != "duplicate":
            continue
        original = items[item["duplicateOf"]]
        if original is not None and original["status"] == "error":
            items[index] = {
                "index": index,
                "input": item["input"],
                "status": "error",
                "error": f"duplicate of input {item['duplicateOf']}, which failed to prepare",
            }

    complete = [item for item in items if item is not None]
    ready_count = sum(item["status"] == "ready" for item in complete)
    error_count = sum(item["status"] == "error" for item in complete)
    duplicate_count = sum(item["status"] == "duplicate" for item in complete)
    print(json.dumps({
        "inputCount": len(args.input),
        "readyCount": ready_count,
        "errorCount": error_count,
        "duplicateCount": duplicate_count,
        "items": complete,
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
