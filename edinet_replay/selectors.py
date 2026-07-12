"""``selectors`` — explicit, named, versioned document-selection strategies.

"The latest annual report" is ambiguous once correction filings, resubmissions,
and same-day multiple filings exist. Selection is therefore never an implicit
side effect of retrieval: each strategy is named and versioned, and records the
full candidate set it saw so the choice is auditable and reproducible.

Interface stub (pre-alpha).
"""
from __future__ import annotations

from .models import DocumentRef, SelectionResult

SELECTOR_VERSION = "1.0.0"


def latest_original_filing(
    candidates: list[DocumentRef],
    *,
    parameters: dict | None = None,
) -> SelectionResult:
    """Choose the latest *original* (non-amendment) filing from ``candidates``.

    Returns a :class:`SelectionResult` recording the strategy, its version, the
    chosen ``document_id``, and every candidate id considered.
    """
    raise NotImplementedError
