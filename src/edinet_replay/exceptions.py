"""Exception hierarchy.

Callers catch these instead of transport- or format-specific errors (HTTP, ZIP,
XML). Every error raised by the library derives from :class:`EdinetReplayError`.
"""
from __future__ import annotations


class EdinetReplayError(Exception):
    """Base class for all edinet-replay errors."""


class ConfigurationError(EdinetReplayError):
    """Missing or invalid configuration (e.g. no API key, bad paths)."""


class EdinetApiError(EdinetReplayError):
    """The EDINET API returned an error or an unexpected response."""


class DocumentNotFoundError(EdinetReplayError):
    """A requested document id was not found."""


class PackageValidationError(EdinetReplayError):
    """A submission package failed validation."""


class UnsafeArchiveError(PackageValidationError):
    """A ZIP entry path is unsafe (traversal / absolute / duplicate / symlink)."""


class PackageConflictError(PackageValidationError):
    """A stored package's bytes do not match the expected hash (no silent overwrite)."""


class TaxonomyResolutionError(EdinetReplayError):
    """A taxonomy package could not be pinned, verified, or resolved offline."""


class TaxonomyConflictError(TaxonomyResolutionError):
    """The same taxonomy identifier/version was re-registered with different content."""


class SelectionError(EdinetReplayError):
    """Document selection failed."""


class NoCandidatesError(SelectionError):
    """No document satisfied the selection criteria."""


class ExtractionError(EdinetReplayError):
    """Faithful extraction failed."""


class SchemaValidationError(EdinetReplayError):
    """An instance did not conform to its JSON Schema."""
