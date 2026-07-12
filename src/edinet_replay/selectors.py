"""``selectors`` — explicit, named, versioned document-selection strategies.

Kept in a separate namespace from :mod:`edinet_replay.catalog`'s mechanical
filters. "The latest annual report" is ambiguous once correction filings,
resubmissions, and same-day multiple filings exist, so each strategy is named and
versioned and records the full candidate set it saw.

Interface stub (pre-alpha).
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .models import DocumentMetadata, SelectionRecord

SELECTOR_VERSION = "1.0.0"


def latest_original_filing(
    candidates: list[DocumentMetadata],
    *,
    parameters: Mapping[str, Any] | None = None,
) -> SelectionRecord:
    """Choose the latest *original* (non-amendment) filing from ``candidates``.

    Returns a :class:`SelectionRecord` recording the strategy, its version, the
    chosen ``document_id``, and every candidate id considered.
    """
    raise NotImplementedError
