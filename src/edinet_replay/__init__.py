"""EDINET Replay — reproducible, provenance-preserving extraction for EDINET filings.

Beta. Implemented: the EDINET API v2 retrieval client, CLI ``fetch`` /
``extract`` / ``validate`` / ``inspect``, content hashing, schema validation,
package storage, pinned offline taxonomy resolution, mechanical
cataloging/selection, the resolved-XBRL faithful projection, and a multi-standard
β corpus (JP GAAP / IFRS / US GAAP).
Not yet implemented: the inline-XBRL (IXDS) presentation-provenance layer.
"""
from __future__ import annotations

__version__ = "0.1.0b1"

from .client import EdinetClient
from .hashing import CONTENT_HASH_ALGORITHM, content_sha256_v1, zip_content_sha256_v1

__all__ = [
    "__version__",
    "CONTENT_HASH_ALGORITHM",
    "EdinetClient",
    "content_sha256_v1",
    "zip_content_sha256_v1",
]
