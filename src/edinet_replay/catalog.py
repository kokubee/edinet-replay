"""``catalog`` — mechanical filtering of document lists into candidate sets.

A pure function of objective, recorded criteria (issuer code, document type,
amendment inclusion, submission-date range). It does not decide which single
document is "the" filing — that is the explicit job of
:mod:`edinet_replay.selectors`. The return order is fixed (ascending by
``submit_datetime`` then ``document_id``) and does not depend on input order.
"""
from __future__ import annotations

from collections.abc import Collection, Iterable
from datetime import datetime

from .models import DocumentMetadata

#: EDINET docTypeCode values, named for readability.
DOCUMENT_TYPES: dict[str, str] = {
    "annual_securities_report": "120",
}


def _submitted_at(doc: DocumentMetadata) -> datetime | None:
    if not doc.submit_datetime:
        return None
    try:
        return datetime.fromisoformat(doc.submit_datetime)
    except ValueError:
        return None


def filter_documents(
    documents: Iterable[DocumentMetadata],
    *,
    edinet_code: str | None = None,
    doc_type_codes: Collection[str] | None = None,
    submitted_from: datetime | None = None,
    submitted_to: datetime | None = None,
    include_amendments: bool = True,
) -> list[DocumentMetadata]:
    """Return the subset of ``documents`` matching the given mechanical criteria,
    sorted ascending by ``(submit_datetime, document_id)``.
    """
    result: list[DocumentMetadata] = []
    for doc in documents:
        if edinet_code is not None and doc.edinet_code != edinet_code:
            continue
        if doc_type_codes is not None and doc.doc_type_code not in doc_type_codes:
            continue
        if not include_amendments and doc.is_amendment:
            continue
        if submitted_from is not None or submitted_to is not None:
            ts = _submitted_at(doc)
            if ts is None:
                continue
            if submitted_from is not None and ts < submitted_from:
                continue
            if submitted_to is not None and ts > submitted_to:
                continue
        result.append(doc)
    result.sort(key=lambda d: (d.submit_datetime or "", d.document_id))
    return result
