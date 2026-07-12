"""``catalog`` — mechanical filtering of document lists into candidate sets.

Applies only objective, recorded criteria (issuer code, document type, amendment
inclusion, date range). It does not decide which single document is "the" filing
— that is the explicit job of :mod:`edinet_replay.selectors`.

Interface stub (pre-alpha).
"""
from __future__ import annotations

from .models import DocumentMetadata, DocumentQuery

#: EDINET docTypeCode values, named for readability.
DOCUMENT_TYPES: dict[str, str] = {
    "annual_securities_report": "120",
}


def filter_documents(
    documents: list[DocumentMetadata],
    query: DocumentQuery,
) -> list[DocumentMetadata]:
    """Return the subset of ``documents`` matching ``query``.

    ``query`` should be recorded verbatim in the manifest's ``selection.parameters``
    so the candidate set is reproducible.
    """
    raise NotImplementedError
