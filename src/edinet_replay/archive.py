"""Bounded, streaming access to ZIP entries.

Every code path that opens an untrusted submission or taxonomy ZIP goes through
this module. Entry paths are validated (Zip Slip, absolute paths, symlinks,
duplicates) and declared sizes, compression ratios, in-flight byte counts, and
entry counts are checked *before or while* decompressing, so a malicious archive
cannot exhaust memory before the extraction guardrails run.

Hashing is streamed in fixed-size chunks: no helper here materializes a whole
entry in memory. ``edinet_replay.hashing`` composes the per-entry digests into
the pinned ``entry-path-and-content-sha256-v1`` value.
"""
from __future__ import annotations

import hashlib
import stat
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass

from .exceptions import PackageValidationError, UnsafeArchiveError

CHUNK_SIZE = 1024 * 1024  # 1 MiB


@dataclass(frozen=True)
class ArchiveLimits:
    """Hard limits applied to one archive."""

    max_entries: int = 10_000
    max_total_bytes: int = 2 * 1024**3  # 2 GiB
    max_file_bytes: int = 512 * 1024**2  # 512 MiB
    max_ratio: float = 200  # uncompressed / compressed


DEFAULT_LIMITS = ArchiveLimits()


@dataclass(frozen=True)
class ArchiveEntry:
    """One validated file entry with its streamed SHA-256."""

    path: str
    size_bytes: int
    sha256: str


def normalize_entry_path(raw_path: str) -> str:
    """Normalize a ZIP entry path per v1: ``/`` separators, strip a leading
    ``./``, reject any ``..`` segment (path traversal / Zip Slip). Unicode form
    and case are left unchanged.
    """
    path = raw_path.replace("\\", "/")
    if path.startswith("./"):
        path = path[2:]
    if any(segment == ".." for segment in path.split("/")):
        raise ValueError(f"unsafe path: {raw_path!r}")
    return path


def _has_drive_prefix(name: str) -> bool:
    return len(name) > 1 and name[1] == ":" and name[0].isalpha()


def _validate_info(
    info: zipfile.ZipInfo, *, limits: ArchiveLimits, seen: set[str]
) -> str:
    name = info.filename
    if "\x00" in name:
        raise UnsafeArchiveError(f"NUL in path: {name!r}")
    if name.startswith(("/", "\\")) or _has_drive_prefix(name):
        raise UnsafeArchiveError(f"absolute path: {name!r}")
    if stat.S_ISLNK(info.external_attr >> 16):
        raise UnsafeArchiveError(f"symlink entry: {name!r}")
    try:
        norm = normalize_entry_path(name)
    except ValueError as exc:
        raise UnsafeArchiveError(str(exc)) from exc
    if not norm or norm.endswith("/"):
        raise UnsafeArchiveError(f"invalid entry path: {name!r}")
    if norm in seen:
        raise UnsafeArchiveError(f"duplicate path: {norm!r}")
    seen.add(norm)
    if info.file_size > limits.max_file_bytes:
        raise UnsafeArchiveError(f"file too large: {norm} ({info.file_size})")
    if info.compress_size and info.file_size / info.compress_size > limits.max_ratio:
        raise UnsafeArchiveError(f"compression ratio too high: {norm}")
    return norm


def validated_entries(
    zf: zipfile.ZipFile, *, limits: ArchiveLimits = DEFAULT_LIMITS
) -> list[tuple[zipfile.ZipInfo, str]]:
    """Return ``(info, normalized_path)`` for every file entry.

    Raises :class:`UnsafeArchiveError` when an entry is unsafe or a declared
    limit is exceeded. No entry contents are read.
    """
    infos = [info for info in zf.infolist() if not info.is_dir()]
    if len(infos) > limits.max_entries:
        raise UnsafeArchiveError(f"too many entries: {len(infos)} > {limits.max_entries}")
    seen: set[str] = set()
    total = 0
    validated: list[tuple[zipfile.ZipInfo, str]] = []
    for info in infos:
        norm = _validate_info(info, limits=limits, seen=seen)
        total += info.file_size
        if total > limits.max_total_bytes:
            raise UnsafeArchiveError("total extracted size exceeds limit")
        validated.append((info, norm))
    return validated


def iter_hashed_entries(
    zf: zipfile.ZipFile, *, limits: ArchiveLimits = DEFAULT_LIMITS
) -> Iterator[ArchiveEntry]:
    """Yield each file entry with a streamed SHA-256 and verified byte count.

    Decompression is read in chunks and stopped as soon as the per-file or total
    byte budget is exceeded. A declared-size lie is rejected by comparing the
    streamed byte count with the central-directory size.
    """
    total = 0
    for info, norm in validated_entries(zf, limits=limits):
        digest = hashlib.sha256()
        size = 0
        try:
            with zf.open(info) as src:
                while True:
                    chunk = src.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    size += len(chunk)
                    total += len(chunk)
                    if size > limits.max_file_bytes:
                        raise UnsafeArchiveError(
                            f"file too large: {norm} (>{limits.max_file_bytes})"
                        )
                    if total > limits.max_total_bytes:
                        raise UnsafeArchiveError("total extracted size exceeds limit")
                    digest.update(chunk)
        except (RuntimeError, NotImplementedError, zipfile.BadZipFile, OSError) as exc:
            raise PackageValidationError(
                f"unreadable ZIP entry {norm!r}: {type(exc).__name__}"
            ) from exc
        if size != info.file_size:
            raise UnsafeArchiveError(
                f"entry size mismatch: {norm} (declared {info.file_size}, read {size})"
            )
        yield ArchiveEntry(path=norm, size_bytes=size, sha256=digest.hexdigest())
