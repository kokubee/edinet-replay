"""Content hashing — the pinned ``entry-path-and-content-sha256-v1`` algorithm.

The one fully-specified, dependency-free part of the project, so it is
implemented (not stubbed). It produces the ``content_sha256`` used in both the
manifest's ``source_package`` and ``taxonomy_package``: a normalized,
compression-independent hash of an archive's logical contents. See
``docs/content-hash-v1.md``.

ZIP entry access is delegated to :mod:`edinet_replay.archive`, which enforces
size/ratio/entry limits and streams bytes instead of loading whole entries.
"""
from __future__ import annotations

import hashlib
import os
import zipfile
from collections.abc import Iterable

from .archive import (
    DEFAULT_LIMITS,
    ArchiveLimits,
    iter_hashed_entries,
    normalize_entry_path,
)

CONTENT_HASH_ALGORITHM = "entry-path-and-content-sha256-v1"

__all__ = [
    "CONTENT_HASH_ALGORITHM",
    "content_sha256_from_hashes",
    "content_sha256_v1",
    "normalize_entry_path",
    "sha256_bytes",
    "sha256_file",
    "zip_content_sha256_v1",
]


def content_sha256_from_hashes(files: Iterable[tuple[str, str]]) -> str:
    """Compute ``entry-path-and-content-sha256-v1`` over ``(path, sha256_hex)``.

    ``files`` must contain file entries only. Digests are the SHA-256 of the
    uncompressed content of each file.
    """
    normalized = [
        (normalize_entry_path(path), digest) for path, digest in files
    ]
    records = b"".join(
        path.encode("utf-8") + b"\x00" + file_hash.encode("ascii") + b"\x0a"
        for path, file_hash in sorted(normalized, key=lambda it: it[0].encode("utf-8"))
    )
    return hashlib.sha256(records).hexdigest()


def content_sha256_v1(files: Iterable[tuple[str, bytes]]) -> str:
    """Compute ``entry-path-and-content-sha256-v1`` over ``(path, bytes)`` pairs.

    ``files`` must contain file entries only (the caller excludes directories).
    ``bytes`` is the *uncompressed* content of each file. For archives, prefer
    :func:`zip_content_sha256_v1`, which streams entries under archive limits.
    """
    return content_sha256_from_hashes(
        (path, hashlib.sha256(data).hexdigest()) for path, data in files
    )


def zip_content_sha256_v1(
    zip_path: str | os.PathLike[str], *, limits: ArchiveLimits = DEFAULT_LIMITS
) -> str:
    """``content_sha256_v1`` over a ZIP file's entries (directories excluded).

    Entries are validated and hashed in a bounded stream; unsafe or over-limit
    archives raise :class:`~edinet_replay.exceptions.UnsafeArchiveError`.
    """
    with zipfile.ZipFile(zip_path) as zf:
        entries = list(iter_hashed_entries(zf, limits=limits))
    return content_sha256_from_hashes((entry.path, entry.sha256) for entry in entries)


def sha256_bytes(data: bytes) -> str:
    """SHA-256 hex of raw bytes (used for ``raw_sha256``)."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | os.PathLike[str]) -> str:
    """SHA-256 hex of a file, read in chunks (never loads the file at once)."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
