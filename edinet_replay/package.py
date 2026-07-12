"""``package`` — store, hash, safely extract, and inventory a submission ZIP.

Records both ``raw_sha256`` (byte-exact artifact) and ``content_sha256``
(normalized logical contents, via :mod:`edinet_replay.hashing`). Extraction is
Zip-Slip-safe. Directory entries are excluded from the content hash and inventory.

Interface stub (pre-alpha) — except that content/raw hashing is delegated to the
already-implemented :mod:`edinet_replay.hashing`.
"""
from __future__ import annotations

import os

from .models import StoredPackage


def store(
    raw_bytes: bytes,
    *,
    document_id: str,
    dest_dir: str | os.PathLike[str],
    retrieved_at: str | None = None,
) -> StoredPackage:
    """Persist the raw ZIP and return a :class:`StoredPackage` with dual hashes
    and a per-file inventory. ``retrieved_at`` is provenance only.
    """
    raise NotImplementedError


def extract_safe(
    package_path: str | os.PathLike[str],
    dest_dir: str | os.PathLike[str],
) -> list[str]:
    """Extract the package into ``dest_dir``, rejecting any unsafe (``..``) path.
    Returns the list of extracted file paths.
    """
    raise NotImplementedError


def find_public_doc(package_path: str | os.PathLike[str]) -> list[str]:
    """Return the XBRL/iXBRL entry paths under ``XBRL/PublicDoc/`` (inventory helper)."""
    raise NotImplementedError
