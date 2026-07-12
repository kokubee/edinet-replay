"""``taxonomy`` — register, hash-verify, and offline-resolve a taxonomy package.

The DTS is part of the extraction input. A taxonomy package is pinned by
``raw_sha256`` + ``content_sha256`` and stored under a registry keyed by
identifier/version. Re-registering the same identifier/version with different
content raises :class:`~edinet_replay.exceptions.TaxonomyConflictError` (no silent
update). Resolution is strictly offline; online resolution is disallowed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .exceptions import TaxonomyConflictError
from .hashing import sha256_bytes
from .models import TaxonomyPackage
from .package import extract_safe, inventory

_INDEX = "taxonomy-index.json"


def register(
    package_path: str | os.PathLike[str],
    *,
    identifier: str,
    version: str | None = None,
    registry_dir: str | os.PathLike[str],
) -> TaxonomyPackage:
    """Register a vendored taxonomy package: store it, pin raw+content hashes,
    write a manifest, and safely extract it for offline resolution. Idempotent
    for identical content; conflicting content for the same identifier/version
    raises :class:`TaxonomyConflictError`.
    """
    raw = Path(package_path).read_bytes()
    raw_hash = sha256_bytes(raw)
    content_hash, _ = inventory(raw)
    ver = version or "unversioned"
    home = Path(registry_dir) / identifier / ver
    home.mkdir(parents=True, exist_ok=True)
    index_path = home / _INDEX

    if index_path.exists():
        prev = json.loads(index_path.read_text(encoding="utf-8"))
        if prev["content_sha256"] != content_hash:
            raise TaxonomyConflictError(
                f"{identifier}/{ver} already registered with different content "
                f"({prev['content_sha256'][:12]} != {content_hash[:12]})"
            )
    else:
        (home / "taxonomy.zip").write_bytes(raw)
        extract_safe(home / "taxonomy.zip", home / "extracted")
        index_path.write_text(
            json.dumps(
                {
                    "identifier": identifier,
                    "version": version,
                    "raw_sha256": raw_hash,
                    "content_sha256": content_hash,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    return TaxonomyPackage(
        identifier=identifier,
        path=str(home / "taxonomy.zip"),
        raw_sha256=raw_hash,
        content_sha256=content_hash,
        version=version,
    )


def verify(ref: TaxonomyPackage, package_path: str | os.PathLike[str]) -> bool:
    """Return True iff the package at ``package_path`` matches ``ref``'s hashes."""
    raw = Path(package_path).read_bytes()
    if sha256_bytes(raw) != ref.raw_sha256:
        return False
    content_hash, _ = inventory(raw)
    return content_hash == ref.content_sha256


def offline_config(ref: TaxonomyPackage) -> dict:
    """Return the configuration that pins Arelle to resolve the DTS offline from
    this taxonomy package only. (Arelle wiring is deferred.)
    """
    raise NotImplementedError
