"""``package`` — store, hash, safely extract, and inventory a submission ZIP.

Records both ``raw_sha256`` (byte-exact artifact) and ``content_sha256``
(normalized logical contents, via :mod:`edinet_replay.hashing`). Storage is
idempotent and never overwrites differing bytes. Extraction is Zip-Slip-safe,
rejects duplicate/absolute/symlink entries, and enforces zip-bomb guardrails.
Directory entries are excluded from the content hash and the inventory.
"""
from __future__ import annotations

import io
import json
import os
import stat
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .exceptions import (
    ConfigurationError,
    PackageConflictError,
    PackageValidationError,
    UnsafeArchiveError,
)
from .hashing import content_sha256_v1, normalize_entry_path, sha256_bytes
from .models import AcquisitionRecord, PackageEntry, SelectionRecord, SourcePackage

# Zip-bomb guardrails (defaults; override per call).
DEFAULT_MAX_ENTRIES = 10_000
DEFAULT_MAX_TOTAL_BYTES = 2 * 1024**3  # 2 GiB
DEFAULT_MAX_FILE_BYTES = 512 * 1024**2  # 512 MiB
DEFAULT_MAX_RATIO = 200  # uncompressed / compressed
ACQUISITION_RECORD_SUFFIX = ".acquisition.json"


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


def acquisition_record_path(package_path: str | os.PathLike[str]) -> Path:
    """Return the sidecar path reserved for one content-addressed ZIP."""
    path = Path(package_path)
    if path.suffix != ".zip":
        raise ConfigurationError(f"acquisition records require a .zip package path: {path}")
    return path.with_suffix(ACQUISITION_RECORD_SUFFIX)


def _acquisition_document(record: AcquisitionRecord) -> dict[str, Any]:
    return {
        "acquisition_schema_version": "1.0.0",
        "document_id": record.document_id,
        "raw_sha256": record.raw_sha256,
        "content_sha256": record.content_sha256,
        "retrieval": {
            "retrieved_at": record.retrieved_at,
            "api_version": record.api_version,
        },
        "selection": asdict(record.selection),
    }


def write_acquisition_record(
    package: SourcePackage,
    *,
    api_version: str,
    selection: SelectionRecord,
) -> Path:
    """Write immutable retrieval provenance beside ``package``.

    Repeated writes of identical evidence are safe. Differing evidence for the
    same raw package is rejected rather than silently overwritten.
    """
    if not package.retrieved_at:
        raise ConfigurationError("cannot record an acquisition without retrieved_at")
    record = AcquisitionRecord(
        document_id=package.document_id,
        raw_sha256=package.raw_sha256,
        content_sha256=package.content_sha256,
        retrieved_at=package.retrieved_at,
        api_version=api_version,
        selection=selection,
    )
    path = acquisition_record_path(package.path)
    body = json.dumps(_acquisition_document(record), ensure_ascii=False, indent=2) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != body:
            raise PackageConflictError(f"acquisition record at {path} differs from new evidence")
        return path
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(body, encoding="utf-8")
    os.replace(temporary, path)
    return path


def load_acquisition_record(
    record_path: str | os.PathLike[str],
    *,
    package: SourcePackage,
) -> AcquisitionRecord:
    """Load an acquisition record and verify that it belongs to ``package``."""
    path = Path(record_path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        retrieval = value["retrieval"]
        selection_value = value["selection"]
        selection = SelectionRecord(
            selected_by=selection_value["selected_by"],
            selector_version=selection_value["selector_version"],
            selected_document_id=selection_value["selected_document_id"],
            candidate_document_ids=list(selection_value["candidate_document_ids"]),
            parameters=selection_value["parameters"],
        )
        record = AcquisitionRecord(
            document_id=value["document_id"],
            raw_sha256=value["raw_sha256"],
            content_sha256=value["content_sha256"],
            retrieved_at=retrieval["retrieved_at"],
            api_version=retrieval["api_version"],
            selection=selection,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"invalid acquisition record: {path}") from exc

    if value.get("acquisition_schema_version") != "1.0.0":
        raise ConfigurationError(f"unsupported acquisition record version: {path}")
    if (
        record.document_id != package.document_id
        or record.raw_sha256 != package.raw_sha256
        or record.content_sha256 != package.content_sha256
    ):
        raise ConfigurationError(f"acquisition record does not match package bytes: {path}")
    if record.selection.selected_document_id != package.document_id:
        raise ConfigurationError(
            f"acquisition selection does not match package document_id: {path}"
        )
    return record


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


_MANIFEST_NS = "{http://disclosure.edinet-fsa.go.jp/2013/manifest}"
_PUBLIC_DOC_PREFIX = "XBRL/PublicDoc/"


def infer_document_id(package_path: str | os.PathLike[str]) -> str | None:
    """Infer a document id from the content-addressed store layout.

    Recognizes ``.../packages/{document_id}/{raw_sha256}.zip`` (the layout
    written by :func:`store`). Returns ``None`` when the path does not match.
    """
    path = Path(package_path)
    if path.parent.parent.name != "packages":
        return None
    doc_id = path.parent.name
    if not doc_id or doc_id in {".", ".."}:
        return None
    return doc_id


def source_package_from_path(
    package_path: str | os.PathLike[str],
    *,
    document_id: str,
    retrieved_at: str | None = None,
) -> SourcePackage:
    """Build a :class:`SourcePackage` from an on-disk ZIP without re-storing it."""
    path = Path(package_path)
    raw = path.read_bytes()
    content_hash, entries = inventory(raw)
    return SourcePackage(
        document_id=document_id,
        path=str(path.resolve()),
        raw_sha256=sha256_bytes(raw),
        content_sha256=content_hash,
        size_bytes=len(raw),
        retrieved_at=retrieved_at,
        entries=entries,
    )


def select_preferred_xbrl(extracted_dir: str | os.PathLike[str]) -> tuple[str, dict]:
    """Choose the preferred resolved XBRL instance under ``XBRL/PublicDoc/``.

    Selection order (deterministic, never implicit when ambiguous):

    1. ``manifest_PublicDoc.xml`` ``instance@preferredFilename`` when present
       and the file exists.
    2. Exactly one ``*.xbrl`` file under PublicDoc.

    Returns ``(package_relative_path, extraction_source)`` where
    ``extraction_source`` is suitable for an extraction-manifest
    ``extraction_source`` object (``kind`` = ``xbrl-instance``).
    """
    import xml.etree.ElementTree as ET

    root = Path(extracted_dir)
    public = root / "XBRL" / "PublicDoc"
    if not public.is_dir():
        raise PackageValidationError(
            f"package has no XBRL/PublicDoc/ directory under {root}"
        )

    manifest_path = public / "manifest_PublicDoc.xml"
    if manifest_path.is_file():
        try:
            tree = ET.parse(manifest_path)
        except ET.ParseError as exc:
            raise PackageValidationError(
                f"unreadable manifest_PublicDoc.xml: {exc}"
            ) from exc
        for inst in tree.getroot().iter(_MANIFEST_NS + "instance"):
            preferred = (inst.get("preferredFilename") or "").strip()
            if not preferred:
                continue
            # preferredFilename is a bare basename inside PublicDoc.
            candidate = public / preferred
            if not candidate.is_file():
                raise PackageValidationError(
                    f"manifest preferredFilename {preferred!r} not found under "
                    f"XBRL/PublicDoc/"
                )
            rel = _PUBLIC_DOC_PREFIX + preferred
            return rel, {
                "kind": "xbrl-instance",
                "package_path": rel,
                "selected_from_manifest": True,
                "preferred_filename": True,
            }

    xbrls = sorted(p.name for p in public.iterdir() if p.is_file() and p.suffix == ".xbrl")
    if len(xbrls) == 1:
        rel = _PUBLIC_DOC_PREFIX + xbrls[0]
        return rel, {
            "kind": "xbrl-instance",
            "package_path": rel,
            "selected_from_manifest": False,
            "preferred_filename": False,
        }
    if not xbrls:
        raise PackageValidationError("no .xbrl instance under XBRL/PublicDoc/")
    raise PackageValidationError(
        "multiple .xbrl instances under XBRL/PublicDoc/ and no usable "
        f"manifest preferredFilename: {xbrls}"
    )
