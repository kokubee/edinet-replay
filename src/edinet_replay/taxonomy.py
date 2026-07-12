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
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .exceptions import TaxonomyConflictError, TaxonomyResolutionError, UnsafeArchiveError
from .hashing import sha256_bytes
from .models import TaxonomyPackage
from .package import extract_safe, inventory

_INDEX = "taxonomy-index.json"

#: EDINET taxonomy files are referenced under this host; only it is seeded.
EDINET_TAXONOMY_HOST = "disclosure.edinet-fsa.go.jp"


@dataclass(frozen=True)
class OfflineArelleConfig:
    """An isolated, content-hash-namespaced Arelle web cache for offline
    resolution of one pinned taxonomy. Points Arelle at ``web_cache_dir`` instead
    of its global cache, so taxonomy swaps and other projects are unaffected.
    """

    taxonomy_id: str
    taxonomy_content_sha256: str
    web_cache_dir: str
    work_offline: bool = True


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


def _find_taxonomy_root(extracted_dir: str | os.PathLike[str]) -> Path:
    """Locate the ``.../taxonomy`` directory inside an extracted FSA package
    (the FSA zip nests it under Japanese-named directories).
    """
    base = Path(extracted_dir)
    for p in base.rglob("taxonomy"):
        if p.is_dir() and any((p / s).is_dir() for s in ("jppfs", "jpcrp", "jpdei")):
            return p
    raise TaxonomyResolutionError(f"no taxonomy/ root with EDINET series under {base}")


def seed_arelle_web_cache(
    extracted_dir: str | os.PathLike[str],
    *,
    taxonomy_id: str,
    content_sha256: str,
    cache_root: str | os.PathLike[str],
) -> OfflineArelleConfig:
    """Copy the pinned taxonomy into an isolated web cache namespaced by the
    taxonomy content hash, so ``http://disclosure.edinet-fsa.go.jp/taxonomy/...``
    resolves offline. Verifies each copied file matches the source. Idempotent.
    """
    tx_root = _find_taxonomy_root(extracted_dir)
    namespace = Path(cache_root) / content_sha256
    dest = namespace / "http" / EDINET_TAXONOMY_HOST / "taxonomy"
    if not dest.exists():
        tmp = dest.with_name("taxonomy.partial")
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(tx_root, tmp)
        # verify copy fidelity
        for src in tx_root.rglob("*"):
            if src.is_file():
                rel = src.relative_to(tx_root)
                if sha256_bytes((tmp / rel).read_bytes()) != sha256_bytes(src.read_bytes()):
                    raise TaxonomyResolutionError(f"copy hash mismatch: {rel}")
        os.replace(tmp, dest)
    return OfflineArelleConfig(
        taxonomy_id=taxonomy_id,
        taxonomy_content_sha256=content_sha256,
        web_cache_dir=str(namespace),
    )


def verify_required_urls(config: OfflineArelleConfig, urls: list[str]) -> dict:
    """Return ``{'resolved': n, 'missing': [...]}`` for taxonomy ``urls`` against
    the isolated cache. Enforces the EDINET host allowlist and rejects traversal.
    """
    base = Path(config.web_cache_dir) / "http" / EDINET_TAXONOMY_HOST
    resolved, missing = 0, []
    for url in urls:
        parsed = urlparse(url)
        if parsed.hostname != EDINET_TAXONOMY_HOST:
            missing.append(url)
            continue
        rel = parsed.path.lstrip("/")
        if ".." in rel.split("/"):
            raise UnsafeArchiveError(f"traversal in url: {url}")
        if (base / rel).is_file():
            resolved += 1
        else:
            missing.append(url)
    return {"resolved": resolved, "missing": missing}
