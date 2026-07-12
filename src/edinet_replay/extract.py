"""``extract`` — project Arelle's model onto the faithful-filing schema.

Arelle resolves XBRL / Inline XBRL semantics (context, dimension, unit, accuracy);
this module maps that model to the ``faithful-filing`` schema, attaches
EDINET-specific source references, and builds the paired ``extraction-manifest``.
Arelle-specific code is deferred; the initial shape is a protocol.
"""
from __future__ import annotations

import re
from typing import Protocol

from .models import (
    ExtractionConfiguration,
    ExtractionManifest,
    FaithfulFiling,
    SelectionRecord,
    SourcePackage,
    TaxonomyPackage,
)
from .taxonomy import OfflineArelleConfig

FAITHFUL_FILING_SCHEMA_VERSION = "1.0.0"
MANIFEST_SCHEMA_VERSION = "1.0.0"

_TAXO_URL = re.compile(r"https?://[^\s'\"<>]+")
_MISSING_HINTS = ("offline", "unable to", "not loadable", "cannot", "no such", "failed to load")


def load_offline(entry_point: str, config: OfflineArelleConfig):
    """Load ``entry_point`` through Arelle with the network blocked, resolving the
    DTS only from the isolated taxonomy cache in ``config``. Arelle is imported
    lazily (requires the ``[xbrl]`` extra). Returns ``(cntlr, model, missing_urls)``
    where ``missing_urls`` is the sorted list of remote references Arelle could
    not resolve offline (empty means fully resolved).
    """
    from arelle import Cntlr

    cntlr = Cntlr.Cntlr(logFileName="logToBuffer")
    cntlr.webCache.cacheDir = config.web_cache_dir
    cntlr.webCache.workOffline = True
    model = cntlr.modelManager.load(str(entry_point))
    missing: set[str] = set()
    for rec in getattr(cntlr.logHandler, "logRecordBuffer", []):
        msg = rec.getMessage()
        if any(h in msg.lower() for h in _MISSING_HINTS):
            missing.update(_TAXO_URL.findall(msg))
    return cntlr, model, sorted(missing)


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
