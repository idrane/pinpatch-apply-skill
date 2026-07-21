#!/usr/bin/env python3
"""Safely copy or extract one PinPatch export into an isolated working root."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


MAX_MEMBERS = 20_000
MAX_MEMBER_BYTES = 512 * 1024 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
MAX_RATIO = 1_000
MAX_SEARCH_DEPTH = 4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="ZIP, PinPatch root, or path inside it")
    parser.add_argument("--work-dir", type=Path, required=True, help="Writable parent for an isolated work directory")
    return parser.parse_args()


def is_pinpatch_root(path: Path) -> bool:
    return path.is_dir() and (path / "pins").is_dir() and (path / "screens").is_dir()


def reject_links(root: Path) -> None:
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in directories + files:
            path = current_path / name
            if path.is_symlink():
                raise ValueError(f"symbolic links are not allowed: {path}")


def ancestors(path: Path):
    current = path if path.is_dir() else path.parent
    yield current
    yield from current.parents


def bounded_candidates(start: Path) -> list[Path]:
    candidates: list[Path] = []
    queue: list[tuple[Path, int]] = [(start, 0)]
    while queue:
        current, depth = queue.pop(0)
        if is_pinpatch_root(current):
            candidates.append(current.resolve())
            continue
        if depth >= MAX_SEARCH_DEPTH:
            continue
        try:
            children = sorted(child for child in current.iterdir() if child.is_dir() and not child.is_symlink())
        except OSError as error:
            raise ValueError(f"cannot inspect input directory {current}: {error}") from error
        queue.extend((child, depth + 1) for child in children)
    return candidates


def locate_directory_root(source: Path) -> Path:
    for candidate in ancestors(source):
        if is_pinpatch_root(candidate):
            return candidate.resolve()
    if not source.is_dir():
        raise ValueError("file is not located inside a PinPatch root")
    candidates = sorted(set(bounded_candidates(source)))
    if len(candidates) != 1:
        raise ValueError(f"expected exactly one PinPatch root, found {len(candidates)}")
    return candidates[0]


def safe_member_path(info: zipfile.ZipInfo) -> PurePosixPath:
    name = info.filename
    if not name or "\\" in name or "\x00" in name:
        raise ValueError(f"unsafe archive member path: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError(f"unsafe archive member path: {name!r}")
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise ValueError(f"symbolic links are not allowed in archives: {name}")
    if info.flag_bits & 0x1:
        raise ValueError(f"encrypted archive members are not supported: {name}")
    if info.file_size > MAX_MEMBER_BYTES:
        raise ValueError(f"archive member exceeds size limit: {name}")
    if info.file_size and info.compress_size == 0:
        raise ValueError(f"archive member has an invalid expansion ratio: {name}")
    if info.compress_size and info.file_size / info.compress_size > MAX_RATIO:
        raise ValueError(f"archive member exceeds expansion ratio limit: {name}")
    return path


def extract_zip(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(source) as archive:
        members = archive.infolist()
        if len(members) > MAX_MEMBERS:
            raise ValueError(f"archive has too many members: {len(members)}")
        total = 0
        normalized: set[str] = set()
        checked: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
        for info in members:
            member_path = safe_member_path(info)
            key = member_path.as_posix().rstrip("/")
            if key in normalized:
                raise ValueError(f"duplicate archive member path: {key}")
            normalized.add(key)
            total += info.file_size
            if total > MAX_TOTAL_BYTES:
                raise ValueError("archive exceeds total uncompressed size limit")
            checked.append((info, member_path))

        for info, member_path in checked:
            target = destination.joinpath(*member_path.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source_handle, target.open("xb") as target_handle:
                shutil.copyfileobj(source_handle, target_handle, length=1024 * 1024)


def prepare_one(input_path: Path, work_dir: Path) -> dict[str, str]:
    session: Path | None = None
    try:
        source = input_path.expanduser().resolve(strict=True)
        work_parent = work_dir.expanduser().resolve()
        work_parent.mkdir(parents=True, exist_ok=True)
        if not work_parent.is_dir():
            raise ValueError(f"work directory is not a directory: {work_parent}")

        session = Path(tempfile.mkdtemp(prefix="pinpatch-export-", dir=work_parent))
        if source.is_file() and source.suffix.lower() == ".zip":
            extracted = session / "extracted"
            extracted.mkdir()
            extract_zip(source, extracted)
            candidates = sorted(set(bounded_candidates(extracted)))
            if len(candidates) != 1:
                raise ValueError(f"expected exactly one PinPatch root in archive, found {len(candidates)}")
            root = candidates[0]
            input_type = "zip"
        else:
            source_root = locate_directory_root(source)
            reject_links(source_root)
            copied = session / "PinPatch"
            shutil.copytree(source_root, copied)
            root = copied.resolve()
            input_type = "directory" if source.is_dir() else "inner-file"

        return {
            "input": str(source),
            "inputType": input_type,
            "root": str(root),
            "workDirectory": str(session),
        }
    except Exception:
        if session is not None:
            shutil.rmtree(session, ignore_errors=True)
        raise


def main() -> int:
    try:
        args = parse_args()
        result = prepare_one(args.input, args.work_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(f"prepare_input: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
