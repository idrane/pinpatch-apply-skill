#!/usr/bin/env python3
"""Package multiple prepared PinPatch roots concurrently without overwriting."""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from package_processed import package_one


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, action="append", required=True, help="Repeat for each prepared root")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for numbered result archives")
    parser.add_argument("--jobs", type=int, default=4, help="Concurrent packages (1-16, default: 4)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.jobs <= 16:
        print("package_batch: --jobs must be between 1 and 16", file=sys.stderr)
        return 2
    output_dir = args.output_dir.expanduser().resolve()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        print(f"package_batch: {error}", file=sys.stderr)
        return 2

    items: list[dict[str, object] | None] = [None] * len(args.root)
    width = max(3, len(str(len(args.root))))
    with ThreadPoolExecutor(max_workers=min(args.jobs, len(args.root))) as executor:
        jobs = {}
        for index, root in enumerate(args.root):
            output = output_dir / f"PinPatch-processed-{index + 1:0{width}d}.zip"
            jobs[executor.submit(package_one, root, output)] = (index, output)
        for future in as_completed(jobs):
            index, output = jobs[future]
            try:
                written = future.result()
                items[index] = {"index": index, "root": str(args.root[index]), "status": "ready", "output": str(written)}
            except Exception as error:
                items[index] = {"index": index, "root": str(args.root[index]), "status": "error", "output": str(output), "error": str(error)}

    complete = [item for item in items if item is not None]
    error_count = sum(item["status"] == "error" for item in complete)
    print(json.dumps({
        "rootCount": len(args.root),
        "readyCount": len(complete) - error_count,
        "errorCount": error_count,
        "items": complete,
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
