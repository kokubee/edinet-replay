"""``extract`` — project Arelle's model onto the faithful-filing schema.

Arelle resolves XBRL / Inline XBRL semantics (context, dimension, unit, accuracy);
this module maps that model to the ``faithful-filing`` schema, attaches
EDINET-specific source references, and builds the paired ``extraction-manifest``.
Arelle-specific code is deferred; the initial shape is a protocol.
"""
from __future__ import annotations

from typing import Protocol

from .models import (
    ExtractionConfiguration,
    ExtractionManifest,
    FaithfulFiling,
    SelectionRecord,
    SourcePackage,
    TaxonomyPackage,
)

FAITHFUL_FILING_SCHEMA_VERSION = "1.0.0"
MANIFEST_SCHEMA_VERSION = "1.0.0"


class FaithfulExtractor(Protocol):
    """Produces a faithful filing from a stored package and pinned taxonomy."""

    def extract(
        self,
        package: SourcePackage,
        taxonomy: TaxonomyPackage,
        *,
        configuration: ExtractionConfiguration | None = None,
    ) -> FaithfulFiling: ...


def build_manifest(
    package: SourcePackage,
    taxonomy: TaxonomyPackage,
    selection: SelectionRecord,
    *,
    arelle_version: str,
    extractor_version: str,
    configuration: ExtractionConfiguration | None = None,
) -> ExtractionManifest:
    """Return an ``extraction-manifest`` document recording the full reproduction
    identity. Conforms to ``extraction-manifest-1.0.0.schema.json``. Never
    contains secrets.
    """
    raise NotImplementedError
