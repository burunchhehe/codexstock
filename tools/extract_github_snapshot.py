from __future__ import annotations

import argparse
import json
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath


def safe_target(root: Path, relative: PurePosixPath) -> Path:
    target = root.joinpath(*relative.parts).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"archive path escaped destination: {relative}")
    return target


def stripped_path(name: str) -> PurePosixPath | None:
    parts = PurePosixPath(name).parts
    if len(parts) <= 1:
        return None
    relative = PurePosixPath(*parts[1:])
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"unsafe archive path: {name}")
    return relative


def extract_snapshot(archive: Path, destination: Path, vault_root: Path) -> dict[str, int]:
    archive = archive.resolve()
    destination = destination.resolve()
    vault_root = vault_root.resolve()
    if not archive.is_file():
        raise FileNotFoundError(archive)
    if destination == vault_root or vault_root not in destination.parents:
        raise ValueError("destination must be a child of the source vault")
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    symlinks: list[tuple[Path, str]] = []
    file_count = 0
    total_bytes = 0
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        expanded_bytes = sum(max(0, item.file_size) for item in members)
        if expanded_bytes > 8 * 1024 * 1024 * 1024:
            raise ValueError("archive expands beyond the 8 GiB safety limit")
        for info in members:
            relative = stripped_path(info.filename)
            if relative is None:
                continue
            target = safe_target(destination, relative)
            mode = info.external_attr >> 16
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if stat.S_ISLNK(mode):
                symlinks.append((target, bundle.read(info).decode("utf-8", errors="strict")))
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
            file_count += 1
            total_bytes += info.file_size

    resolved_links = 0
    fallback_links = 0
    for link_path, link_target in symlinks:
        link_path.parent.mkdir(parents=True, exist_ok=True)
        target = (link_path.parent / link_target).resolve()
        if target != destination and destination not in target.parents:
            raise ValueError(f"symbolic link escaped destination: {link_path}")
        if target.is_file():
            shutil.copy2(target, link_path)
            total_bytes += link_path.stat().st_size
            resolved_links += 1
        else:
            link_path.write_text(link_target, encoding="utf-8")
            total_bytes += link_path.stat().st_size
            fallback_links += 1
        file_count += 1

    return {
        "file_count": file_count,
        "total_bytes": total_bytes,
        "symlink_count": len(symlinks),
        "resolved_symlink_count": resolved_links,
        "fallback_symlink_count": fallback_links,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely extract a GitHub source snapshot on Windows")
    parser.add_argument("archive", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("vault_root", type=Path)
    args = parser.parse_args()
    result = extract_snapshot(args.archive, args.destination, args.vault_root)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
