"""``catalog`` — mechanical filtering of document lists into candidate sets.

This layer applies only objective, recorded criteria (issuer code, document
type, amendment inclusion, date range). It does **not** decide which single
document is "the" filing — that is the explicit job of :mod:`edinet_replay.selectors`.

Interface stub (pre-alpha).
"""
from __future__ import annotations

from .models import DocumentRef

#: EDINET docTypeCode values, named for readability.
DOCUMENT_TYPES: dict[str, str] = {
    "annual_securities_report": "120",
}


def filter_documents(
    documents: list[DocumentRef],
    *,
    edinet_code: str | None = None,
    document_type: str | None = None,
    include_amendments: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[DocumentRef]:
    """Return the subset of ``documents`` matching the given mechanical criteria.

    The exact parameters used should be recorded verbatim in the manifest's
    ``selection.parameters`` so the candidate set is reproducible.
    """
    raise NotImplementedError
