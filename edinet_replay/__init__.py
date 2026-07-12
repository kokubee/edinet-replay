"""EDINET Replay — reproducible, provenance-preserving extraction for EDINET filings.

Pre-alpha. Only :mod:`edinet_replay.hashing` is implemented; the retrieval,
package, taxonomy, selection, and extraction modules are interface stubs whose
bodies raise :class:`NotImplementedError`.
"""
from __future__ import annotations

__version__ = "0.1.0"

from .hashing import CONTENT_HASH_ALGORITHM, content_sha256_v1, zip_content_sha256_v1

__all__ = [
    "__version__",
    "CONTENT_HASH_ALGORITHM",
    "content_sha256_v1",
    "zip_content_sha256_v1",
]
