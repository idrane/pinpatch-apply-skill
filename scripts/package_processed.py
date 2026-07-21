#!/usr/bin/env python3
"""Package a prepared PinPatch working root as a new ZIP without overwriting."""

from __future__ import annotations

import argparse
import os
import sys
import zipfile
from pathlib import Path


MAX_FILES = 20_000
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Prepared PinPatch root")
    parser.add_argument("--output", type=Path, required=True, help="New .zip path")
    return parser.parse_args()


def package_one(root_path: Path, output_path: Path) -> Path:
    output: Path | None = None
    output_started = False
    try:
        root = root_path.expanduser().resolve(strict=True)
        output = output_path.expanduser().resolve()
        if not root.is_dir() or not (root / "pins").is_dir() or not (root / "screens").is_dir():
            raise ValueError(f"not a PinPatch root: {root}")
        if output.suffix.lower() != ".zip":
            raise ValueError("output must have a .zip extension")
        if output.exists():
            raise ValueError(f"refusing to overwrite existing output: {output}")
        try:
            output.relative_to(root)
        except ValueError:
            pass
        else:
            raise ValueError("output must not be inside the PinPatch root")

        entries: list[Path] = []
        total = 0
        for current, directories, files in os.walk(root, followlinks=False):
            current_path = Path(current)
            for name in directories + files:
                path = current_path / name
                if path.is_symlink():
                    raise ValueError(f"symbolic links are not allowed: {path}")
            for name in files:
                path = current_path / name
                entries.append(path)
                total += path.stat().st_size
                if len(entries) > MAX_FILES:
                    raise ValueError("PinPatch root contains too many files")
                if total > MAX_TOTAL_BYTES:
                    raise ValueError("PinPatch root exceeds packaging size limit")

        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            archive = zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6)
        except FileExistsError:
            raise ValueError(f"refusing to overwrite existing output: {output}") from None
        output_started = True
        with archive:
            for path in sorted(entries):
                archive.write(path, (Path("PinPatch") / path.relative_to(root)).as_posix())
        return output
    except Exception:
        if output is not None and output_started:
            try:
                output.unlink()
            except FileNotFoundError:
                pass
        raise


def main() -> int:
    try:
        args = parse_args()
        output = package_one(args.root, args.output)
        print(str(output))
        return 0
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(f"package_processed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
