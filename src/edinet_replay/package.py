"""``package`` — store, hash, safely extract, and inventory a submission ZIP.

Records both ``raw_sha256`` (byte-exact artifact) and ``content_sha256``
(normalized logical contents, via :mod:`edinet_replay.hashing`). Storage is
idempotent and never overwrites differing bytes. Extraction is Zip-Slip-safe,
rejects duplicate/absolute/symlink entries, and enforces zip-bomb guardrails.
Directory entries are excluded from the content hash and the inventory.
"""
from __future__ import annotations

import io
import os
import stat
import zipfile
from pathlib import Path

from .exceptions import PackageConflictError, PackageValidationError, UnsafeArchiveError
from .hashing import content_sha256_v1, normalize_entry_path, sha256_bytes
from .models import PackageEntry, SourcePackage

# Zip-bomb guardrails (defaults; override per call).
DEFAULT_MAX_ENTRIES = 10_000
DEFAULT_MAX_TOTAL_BYTES = 2 * 1024**3  # 2 GiB
DEFAULT_MAX_FILE_BYTES = 512 * 1024**2  # 512 MiB
DEFAULT_MAX_RATIO = 200  # uncompressed / compressed


def _file_entries(data: bytes) -> list[tuple[str, bytes, int]]:
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise PackageValidationError("not a ZIP archive")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return [
            (info.filename, zf.read(info.filename), info.file_size)
            for info in zf.infolist()
            if not info.is_dir()
        ]


def inventory(data: bytes) -> tuple[str, list[PackageEntry]]:
    """Return ``(content_sha256, entries)`` for ZIP ``data`` (files only)."""
    raw_entries = _file_entries(data)
    content_hash = content_sha256_v1([(name, body) for name, body, _ in raw_entries])
    entries = [
        PackageEntry(
            path=normalize_entry_path(name), sha256=sha256_bytes(body), size_bytes=size
        )
        for name, body, size in raw_entries
    ]
    entries.sort(key=lambda e: e.path.encode("utf-8"))
    return content_hash, entries


def store(
    raw_bytes: bytes,
    *,
    document_id: str,
    dest_dir: str | os.PathLike[str],
    retrieved_at: str | None = None,
) -> SourcePackage:
    """Persist the raw ZIP under ``dest_dir/packages/{document_id}/{raw_sha256}.zip``
    and return a :class:`SourcePackage` with dual hashes and inventory. Idempotent:
    re-storing identical bytes is a no-op; differing bytes at the same path raise
    :class:`PackageConflictError`.
    """
    raw_hash = sha256_bytes(raw_bytes)
    content_hash, entries = inventory(raw_bytes)  # also validates the ZIP
    base = Path(dest_dir) / "packages" / document_id
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{raw_hash}.zip"
    if path.exists():
        if sha256_bytes(path.read_bytes()) != raw_hash:
            raise PackageConflictError(f"stored bytes at {path} do not match {raw_hash}")
    else:
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(raw_bytes)
        os.replace(tmp, path)
    return SourcePackage(
        document_id=document_id,
        path=str(path),
        raw_sha256=raw_hash,
        content_sha256=content_hash,
        size_bytes=len(raw_bytes),
        retrieved_at=retrieved_at,
        entries=entries,
    )


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK(info.external_attr >> 16)


def extract_safe(
    package_path: str | os.PathLike[str],
    dest_dir: str | os.PathLike[str],
    *,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_ratio: float = DEFAULT_MAX_RATIO,
) -> list[str]:
    """Extract ``package_path`` into ``dest_dir``, rejecting unsafe entries and
    enforcing zip-bomb limits. Returns the list of written file paths.
    """
    dest = Path(dest_dir).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    seen: set[str] = set()
    total = 0
    with zipfile.ZipFile(package_path) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > max_entries:
            raise UnsafeArchiveError(f"too many entries: {len(infos)} > {max_entries}")
        for info in infos:
            name = info.filename
            if "\x00" in name:
                raise UnsafeArchiveError(f"NUL in path: {name!r}")
            if name.startswith(("/", "\\")) or (len(name) > 1 and name[1] == ":"):
                raise UnsafeArchiveError(f"absolute path: {name!r}")
            if _is_symlink(info):
                raise UnsafeArchiveError(f"symlink entry: {name!r}")
            try:
                norm = normalize_entry_path(name)
            except ValueError as exc:
                raise UnsafeArchiveError(str(exc)) from exc
            if norm in seen:
                raise UnsafeArchiveError(f"duplicate path: {norm!r}")
            seen.add(norm)
            if info.file_size > max_file_bytes:
                raise UnsafeArchiveError(f"file too large: {norm} ({info.file_size})")
            if info.compress_size and info.file_size / info.compress_size > max_ratio:
                raise UnsafeArchiveError(f"compression ratio too high: {norm}")
            total += info.file_size
            if total > max_total_bytes:
                raise UnsafeArchiveError("total extracted size exceeds limit")
            target = (dest / norm).resolve()
            if target != dest and not str(target).startswith(str(dest) + os.sep):
                raise UnsafeArchiveError(f"path escapes destination: {norm!r}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info.filename))
            written.append(str(target))
    return written


def find_public_doc(package_path: str | os.PathLike[str]) -> list[str]:
    """Return sorted XBRL/iXBRL entry paths under ``XBRL/PublicDoc/``."""
    with zipfile.ZipFile(package_path) as zf:
        return sorted(
            normalize_entry_path(i.filename)
            for i in zf.infolist()
            if not i.is_dir()
            and normalize_entry_path(i.filename).startswith("XBRL/PublicDoc/")
        )
