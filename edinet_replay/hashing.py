"""Content hashing — the pinned ``entry-path-and-content-sha256-v1`` algorithm.

This is the one fully-specified, dependency-free part of the project, so it is
implemented (not stubbed). It produces the ``content_sha256`` used in both the
extraction manifest's ``source_package`` and ``taxonomy_package``: a normalized,
compression-independent hash of an archive's logical contents. See
``docs/content-hash-v1.md``.
"""
from __future__ import annotations

import hashlib
import os
import zipfile
from collections.abc import Iterable

CONTENT_HASH_ALGORITHM = "entry-path-and-content-sha256-v1"


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


def content_sha256_v1(files: Iterable[tuple[str, bytes]]) -> str:
    """Compute ``entry-path-and-content-sha256-v1`` over ``(path, bytes)`` pairs.

    ``files`` must contain file entries only (the caller excludes directories).
    ``bytes`` is the *uncompressed* content of each file.
    """
    normalized = [
        (normalize_entry_path(path), hashlib.sha256(data).hexdigest())
        for path, data in files
    ]
    records = b"".join(
        path.encode("utf-8") + b"\x00" + file_hash.encode("ascii") + b"\x0a"
        for path, file_hash in sorted(normalized, key=lambda it: it[0].encode("utf-8"))
    )
    return hashlib.sha256(records).hexdigest()


def zip_content_sha256_v1(zip_path: str | os.PathLike[str]) -> str:
    """``content_sha256_v1`` over a ZIP file's entries (directories excluded)."""
    with zipfile.ZipFile(zip_path) as zf:
        files = [
            (info.filename, zf.read(info.filename))
            for info in zf.infolist()
            if not info.is_dir()
        ]
    return content_sha256_v1(files)


def sha256_bytes(data: bytes) -> str:
    """SHA-256 hex of raw bytes (used for ``raw_sha256``)."""
    return hashlib.sha256(data).hexdigest()
