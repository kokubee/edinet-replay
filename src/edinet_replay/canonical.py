"""Canonical JSON serialization — profile ``edinet-replay-canonical-json-v1``.

Project-specific (see ``docs/canonicalization-v1.md``); NOT a claim of full
RFC 8785 (JCS) conformance. Object member names are sorted by Unicode code point;
arrays preserve producer order (never re-sorted here); UTF-8, no BOM, no
insignificant whitespace, no trailing newline; no Unicode normalization. Financial
values are already strings in the schema, so no number canonicalization applies.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

CANONICAL_JSON_PROFILE = "edinet-replay-canonical-json-v1"


def canonicalize(obj: Any) -> bytes:
    """Serialize ``obj`` to canonical JSON bytes under the profile.

    Uses ``sort_keys`` (Unicode code-point order for member names), no
    whitespace, UTF-8, and no trailing newline. Lists keep their order. NaN/Inf
    are rejected (they cannot occur: financial values are strings).
    """
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(obj: Any) -> str:
    """SHA-256 hex of the canonical JSON bytes of ``obj``."""
    return hashlib.sha256(canonicalize(obj)).hexdigest()
