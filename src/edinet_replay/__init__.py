"""EDINET Replay — reproducible, provenance-preserving extraction for EDINET filings.

Pre-alpha. The content-hash algorithm and schema validation are implemented;
retrieval, package handling, taxonomy resolution, selection, and Arelle-based
extraction are interface stubs whose bodies raise ``NotImplementedError`` (or a
dedicated :mod:`edinet_replay.exceptions` error).
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
