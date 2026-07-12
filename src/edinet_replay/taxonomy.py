"""``taxonomy`` — register, hash-verify, and offline-resolve a taxonomy package.

The DTS is part of the extraction input. A taxonomy package is pinned by
``raw_sha256`` + ``content_sha256`` and resolved strictly offline; online
resolution is disallowed because a change to a remote taxonomy URL would silently
alter output. Failures raise
:class:`~edinet_replay.exceptions.TaxonomyResolutionError`.

Interface stub (pre-alpha).
"""
from __future__ import annotations

import os

from .models import TaxonomyPackage


def register(
    package_path: str | os.PathLike[str],
    *,
    identifier: str,
    version: str | None = None,
) -> TaxonomyPackage:
    """Register a vendored taxonomy package and compute its raw + content hashes."""
    raise NotImplementedError


def verify(ref: TaxonomyPackage, package_path: str | os.PathLike[str]) -> bool:
    """Return True iff the package at ``package_path`` matches ``ref``'s hashes."""
    raise NotImplementedError


def offline_config(ref: TaxonomyPackage) -> dict:
    """Return the configuration that pins Arelle to resolve the DTS offline from
    this taxonomy package only.
    """
    raise NotImplementedError
