"""Typed domain objects passed between the Layer 1 modules.

These describe the *shapes* the interfaces exchange. The on-disk manifest and
faithful-filing artifacts are JSON validated against ``schemas/``; these
dataclasses are the in-process representations.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DocumentRef:
    """One EDINET document as seen in the daily document list."""

    document_id: str
    edinet_code: str | None = None
    submitter_name: str | None = None
    doc_type_code: str | None = None
    description: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    submit_datetime: str | None = None


@dataclass(frozen=True)
class SelectionResult:
    """The explicit outcome of choosing one document from a candidate set."""

    selected_by: str
    selector_version: str
    selected_document_id: str
    candidate_document_ids: list[str]
    parameters: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PackageEntry:
    path: str
    sha256: str
    size_bytes: int | None = None


@dataclass(frozen=True)
class StoredPackage:
    """A downloaded submission ZIP, stored with dual hashes and an inventory."""

    document_id: str
    path: str
    raw_sha256: str
    content_sha256: str
    media_type: str = "application/zip"
    size_bytes: int | None = None
    retrieved_at: str | None = None
    entries: list[PackageEntry] = field(default_factory=list)


@dataclass(frozen=True)
class TaxonomyRef:
    """A pinned, locally vendored taxonomy package for offline DTS resolution."""

    identifier: str
    path: str
    raw_sha256: str
    content_sha256: str
    version: str | None = None
