"""Typed domain objects exchanged between the Layer 1 modules.

Only boundary types are hand-written as dataclasses. The manifest and
faithful-filing *documents* stay as validated mappings rather than hand-mirrored
dataclasses, so the Python types cannot silently drift from the JSON Schemas
(schema validation is mandatory; typed generation can come later).
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DocumentMetadata:
    """One EDINET document as seen in the daily document list."""

    document_id: str
    edinet_code: str | None = None
    submitter_name: str | None = None
    doc_type_code: str | None = None
    description: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    submit_datetime: str | None = None
    is_amendment: bool = False


@dataclass(frozen=True)
class DocumentQuery:
    """Mechanical filter criteria; recorded verbatim in ``selection.parameters``."""

    edinet_code: str | None = None
    document_type: str | None = None
    include_amendments: bool = False
    date_from: str | None = None
    date_to: str | None = None


@dataclass(frozen=True)
class SelectionRecord:
    """The explicit outcome of choosing one document from a candidate set."""

    selected_by: str
    selector_version: str
    selected_document_id: str
    candidate_document_ids: list[str]
    parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PackageEntry:
    path: str
    sha256: str
    size_bytes: int | None = None


@dataclass(frozen=True)
class SourcePackage:
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
class TaxonomyPackage:
    """A pinned, locally vendored taxonomy package for offline DTS resolution."""

    identifier: str
    path: str
    raw_sha256: str
    content_sha256: str
    version: str | None = None


@dataclass(frozen=True)
class ExtractionConfiguration:
    """Output-affecting extraction settings (part of extraction identity)."""

    options: Mapping[str, Any] = field(default_factory=dict)


# Boundary-heavy documents stay as validated mappings, not hand-mirrored dataclasses.
FaithfulFiling = Mapping[str, Any]
ExtractionManifest = Mapping[str, Any]
