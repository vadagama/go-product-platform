"""Portable project copies of approved agent assets; no instruction execution."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

ROOTS = ('.agents', '.claude')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(source: Path, prefix: str, files: dict) -> None:
    if not source.is_dir():
        raise RuntimeError(f'Missing agent assets: {source}')
    for path in sorted(source.rglob('*')):
        if '.git' in path.relative_to(source).parts or '__pycache__' in path.parts:
            continue
        if path.is_symlink():
            raise RuntimeError(f'Agent asset symlinks must be resolved explicitly: {path}')
        if path.is_file():
            dest = str(Path(prefix) / path.relative_to(source))
            if dest in files and digest(files[dest]) != digest(path):
                raise RuntimeError(f'Conflicting agent asset: {dest}')
            files[dest] = path


def install(project: Path, files: dict, previous: dict) -> dict:
    """Preflight all collisions before writing; preserve edits and unmanaged files."""
    for rel in set(files) | set(previous):
        if Path(rel).is_absolute() or '..' in Path(rel).parts:
            raise RuntimeError(f'Unsafe asset path: {rel}')
    hashes = {rel: digest(path) for rel, path in files.items()}
    for root in ROOTS:
        for rel in set(files) | set(previous):
            target = project / root / rel
            if not target.resolve().is_relative_to(project.resolve()):
                raise RuntimeError(f'Asset path escapes project: {target}')
            if target.is_symlink() or any(p.is_symlink() for p in target.parents if p != project):
                raise RuntimeError(f'Asset destination is a symlink: {target}')
            if target.exists() and (not target.is_file() or digest(target) not in {previous.get(rel), hashes.get(rel)}):
                raise RuntimeError(f'Preserving modified/unmanaged asset: {target}')
    for root in ROOTS:
        for rel, source in files.items():
            target = project / root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        for rel in set(previous) - set(files):
            (project / root / rel).unlink(missing_ok=True)
    return hashes


def healthy(project: Path, hashes: dict) -> bool:
    return bool(hashes) and all(
        (project / root / rel).is_file() and digest(project / root / rel) == sha
        for root in ROOTS for rel, sha in hashes.items())
