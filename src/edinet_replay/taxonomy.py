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

#: Default local cache home (taxonomy zips, registry, isolated Arelle web cache).
DEFAULT_CACHE_HOME = Path.home() / ".cache" / "edinet-replay"


def default_taxonomy_zip(identifier: str) -> Path:
    """Conventional path for a pinned FSA ``1c_Taxonomy.zip`` distribution."""
    return DEFAULT_CACHE_HOME / "taxonomies" / identifier / "1c_Taxonomy.zip"


def pins_search_paths(pins_dir: str | os.PathLike[str] | None = None) -> list[Path]:
    """Directories that may hold pin records (``{identifier}.json``)."""
    paths: list[Path] = []
    if pins_dir is not None:
        paths.append(Path(pins_dir))
    env = os.environ.get("EDINET_REPLAY_PINS_DIR")
    if env:
        paths.append(Path(env))
    # Editable / repo checkout: src/edinet_replay/taxonomy.py → repo/taxonomies/
    paths.append(Path(__file__).resolve().parents[2] / "taxonomies")
    paths.append(Path.cwd() / "taxonomies")
    return paths


def load_pin_record(
    identifier: str, *, pins_dir: str | os.PathLike[str] | None = None
) -> dict:
    """Load the pin JSON for ``identifier`` from the first matching pins dir."""
    tried: list[str] = []
    for base in pins_search_paths(pins_dir):
        path = base / f"{identifier}.json"
        tried.append(str(path))
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("identifier") != identifier:
                raise TaxonomyResolutionError(
                    f"pin {path} has identifier {data.get('identifier')!r}, "
                    f"expected {identifier!r}"
                )
            return data
    raise TaxonomyResolutionError(
        f"no pin record for taxonomy {identifier!r}; looked in: {tried}"
    )


def prepare_offline_taxonomy(
    identifier: str,
    *,
    taxonomy_zip: str | os.PathLike[str] | None = None,
    pins_dir: str | os.PathLike[str] | None = None,
    registry_dir: str | os.PathLike[str] | None = None,
    cache_root: str | os.PathLike[str] | None = None,
) -> tuple[TaxonomyPackage, OfflineArelleConfig, dict]:
    """Load a pin, verify the local taxonomy zip hashes, register it, and seed
    an isolated offline Arelle web cache. Returns ``(ref, config, pin)``.
    """
    pin = load_pin_record(identifier, pins_dir=pins_dir)
    zip_path = Path(taxonomy_zip) if taxonomy_zip is not None else default_taxonomy_zip(identifier)
    if not zip_path.is_file():
        source = pin.get("source_url", "(see pin record)")
        raise TaxonomyResolutionError(
            f"taxonomy zip not found at {zip_path}; download from {source} "
            f"into that path, or pass taxonomy_zip="
        )
    raw = zip_path.read_bytes()
    raw_hash = sha256_bytes(raw)
    if raw_hash != pin["raw_sha256"]:
        raise TaxonomyResolutionError(
            f"taxonomy zip raw_sha256 mismatch for {identifier}: "
            f"file={raw_hash[:12]}… pin={pin['raw_sha256'][:12]}…"
        )
    content_hash, _ = inventory(raw)
    if content_hash != pin["content_sha256"]:
        raise TaxonomyResolutionError(
            f"taxonomy zip content_sha256 mismatch for {identifier}: "
            f"file={content_hash[:12]}… pin={pin['content_sha256'][:12]}…"
        )

    reg = Path(registry_dir) if registry_dir is not None else DEFAULT_CACHE_HOME / "registry"
    cache = (
        Path(cache_root)
        if cache_root is not None
        else DEFAULT_CACHE_HOME / "arelle-web-cache"
    )
    version = pin.get("version")
    ref = register(
        zip_path,
        identifier=identifier,
        version=version,
        registry_dir=reg,
    )
    ver = version or "unversioned"
    extracted = reg / identifier / ver / "extracted"
    cfg = seed_arelle_web_cache(
        extracted,
        taxonomy_id=ref.identifier,
        content_sha256=ref.content_sha256,
        cache_root=cache,
    )
    return ref, cfg, pin


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
        # Same logical content but possibly different raw bytes (e.g. the same
        # files re-zipped). The registry keeps the ORIGINAL archive, so return
        # the stored pin — otherwise a manifest could record a raw_sha256 that
        # does not match the archive actually on disk.
        return TaxonomyPackage(
            identifier=prev["identifier"],
            path=str(home / "taxonomy.zip"),
            raw_sha256=prev["raw_sha256"],
            content_sha256=prev["content_sha256"],
            version=prev["version"],
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
