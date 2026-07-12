"""``client`` — EDINET API v2 communication only.

No selection logic and no interpretation live here: the client fetches the daily
document list and downloads raw document packages. The API key is read from the
constructor argument or the ``EDINET_API_KEY`` environment variable and is never
written into outputs, manifests, or logs.

Interface stub (pre-alpha): bodies raise ``NotImplementedError``.
"""
from __future__ import annotations

import os

from .models import DocumentRef

DEFAULT_API_BASE = "https://api.edinet-fsa.go.jp/api/v2"


class EdinetClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        api_base: str = DEFAULT_API_BASE,
        session: object | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("EDINET_API_KEY")
        self.api_base = api_base
        self._session = session

    def list_documents(self, date: str) -> list[DocumentRef]:
        """Return the EDINET document list for a submission date (``YYYY-MM-DD``).

        Faithful: returns what EDINET reports, with no filtering or selection.
        """
        raise NotImplementedError

    def download_document(self, document_id: str) -> bytes:
        """Return the raw submission ZIP bytes for a ``docID``, exactly as received."""
        raise NotImplementedError
