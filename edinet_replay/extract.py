"""``extract`` — produce faithful JSON from Arelle's model, plus the manifest.

Arelle resolves XBRL / Inline XBRL semantics (context, dimension, unit, accuracy);
this module maps that model to the ``faithful-filing`` schema and attaches
EDINET-specific source references, and builds the paired ``extraction-manifest``.
Arelle is imported lazily so the package imports without it installed.

Interface stub (pre-alpha).
"""
from __future__ import annotations

from .models import StoredPackage, TaxonomyRef

FAITHFUL_FILING_SCHEMA_VERSION = "1.0.0"
MANIFEST_SCHEMA_VERSION = "1.0.0"


def extract_faithful(
    package: StoredPackage,
    taxonomy: TaxonomyRef,
    *,
    extractor_version: str,
    configuration: dict | None = None,
) -> dict:
    """Return a ``faithful-filing`` document (dict) for ``package``.

    Resolves the filing through Arelle against the pinned ``taxonomy`` and emits
    OIM-compatible facts with provenance. The result conforms to
    ``schemas/faithful-filing-1.0.0.schema.json``.
    """
    raise NotImplementedError


def build_manifest(
    package: StoredPackage,
    taxonomy: TaxonomyRef,
    selection,  # SelectionResult
    *,
    arelle_version: str,
    extractor_version: str,
    configuration: dict | None = None,
) -> dict:
    """Return an ``extraction-manifest`` document (dict) recording the full
    reproduction identity. Conforms to
    ``schemas/extraction-manifest-1.0.0.schema.json``. Never contains secrets.
    """
    raise NotImplementedError
