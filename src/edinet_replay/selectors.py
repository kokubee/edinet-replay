"""``selectors`` — explicit, named, versioned document-selection strategies.

Kept in a separate namespace from :mod:`edinet_replay.catalog`'s mechanical
filters. "The latest annual report" is ambiguous once correction filings,
resubmissions, and same-day multiple filings exist, so each strategy is named and
versioned, has no hidden criteria, and records the full candidate set it saw.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .exceptions import NoCandidatesError
from .models import DocumentMetadata, SelectionRecord

SELECTOR_VERSION = "1.0.0"


def latest_original_filing(
    candidates: Sequence[DocumentMetadata],
    *,
    parameters: Mapping[str, Any] | None = None,
) -> SelectionRecord:
    """Choose the latest *original* (non-amendment) filing.

    Amendments are excluded. The latest is by ``submit_datetime``, with ties
    broken deterministically by ``document_id``. Raises
    :class:`~edinet_replay.exceptions.NoCandidatesError` if no original filing
    remains. The returned record keeps the full candidate id set (sorted), the
    selector name/version, and the parameters.
    """
    all_ids = sorted(doc.document_id for doc in candidates)
    originals = [doc for doc in candidates if not doc.is_amendment]
    if not originals:
        raise NoCandidatesError("no original (non-amendment) filing among candidates")
    chosen = max(originals, key=lambda d: (d.submit_datetime or "", d.document_id))
    return SelectionRecord(
        selected_by="latest_original_filing",
        selector_version=SELECTOR_VERSION,
        selected_document_id=chosen.document_id,
        candidate_document_ids=all_ids,
        parameters=dict(parameters or {}),
    )
