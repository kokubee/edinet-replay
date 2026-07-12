"""``client`` — EDINET API v2 communication only.

No selection logic and no interpretation: the client fetches the daily document
list and downloads raw document packages. The API key is read from the
constructor argument or the ``EDINET_API_KEY`` environment variable, sent as
the ``Ocp-Apim-Subscription-Key`` request header (verified working against the
live API), and therefore never appears in any URL. It is also never written
into outputs, logs, or exception messages; exception messages never embed full
request URLs.

EDINET-specific status handling (verified against the live API, 2026-07-12):
the API returns **HTTP 200 for every error** and reports the real status in
the body —

- list success: ``{"metadata": {"status": "200", ...}, "results": [...]}``
- invalid/missing key (both endpoints): ``{"StatusCode": 401, "message": ...}``
- unknown docID / bad parameters: ``{"metadata": {"status": "404"|"400", ...}}``
- download success: ``application/octet-stream`` ZIP bytes

Retries are limited to real HTTP 429/5xx transport failures; body-level errors
and other HTTP 4xx are never retried.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from .exceptions import (
    ConfigurationError,
    DocumentNotFoundError,
    EdinetAuthenticationError,
    EdinetRateLimitError,
    EdinetResponseError,
    EdinetTransportError,
)
from .models import DocumentDownload, DocumentListResult, DocumentMetadata

DEFAULT_API_BASE = "https://api.edinet-fsa.go.jp/api/v2"
API_VERSION = "v2"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DOC_ID_RE = re.compile(r"^[A-Za-z0-9]+$")
_ZIP_MAGIC = b"PK"

# EDINET request `type` parameters: 2 = list with full result metadata,
# 1 = the main submission package (XBRL ZIP).
_LIST_TYPE = "2"
_PACKAGE_TYPE = "1"


@dataclass(frozen=True)
class HttpResponse:
    """Transport-level response; header names are matched case-insensitively."""

    status: int
    headers: Mapping[str, str]
    body: bytes

    def content_type(self) -> str:
        for name, value in self.headers.items():
            if name.lower() == "content-type":
                return value
        return ""


class HttpTransport(Protocol):
    """Minimal injectable HTTP layer (tests substitute a fake; no live calls in CI).

    Implementations perform one GET request and return the response whatever its
    HTTP status (4xx/5xx included). They raise ``TimeoutError`` on timeout and
    ``OSError`` on network failure.
    """

    def request(
        self, url: str, *, headers: Mapping[str, str], timeout: float
    ) -> HttpResponse: ...


class UrllibTransport:
    """Default stdlib transport."""

    def request(
        self, url: str, *, headers: Mapping[str, str], timeout: float
    ) -> HttpResponse:
        req = urllib.request.Request(url, headers=dict(headers))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as res:
                return HttpResponse(
                    status=res.status, headers=dict(res.headers), body=res.read()
                )
        except urllib.error.HTTPError as err:
            body = err.read() if err.fp is not None else b""
            return HttpResponse(status=err.code, headers=dict(err.headers or {}), body=body)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _document_from_result(item: Mapping[str, object]) -> DocumentMetadata:
    def _s(key: str) -> str | None:
        value = item.get(key)
        return str(value) if value is not None else None

    doc_id = _s("docID")
    if not doc_id:
        raise EdinetResponseError("EDINET document list entry is missing docID")
    parent = _s("parentDocID")
    return DocumentMetadata(
        document_id=doc_id,
        edinet_code=_s("edinetCode"),
        submitter_name=_s("filerName"),
        doc_type_code=_s("docTypeCode"),
        description=_s("docDescription"),
        period_start=_s("periodStart"),
        period_end=_s("periodEnd"),
        submit_datetime=_s("submitDateTime"),
        is_amendment=parent is not None,
        parent_document_id=parent,
    )


class EdinetClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        api_base: str = DEFAULT_API_BASE,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
        transport: HttpTransport | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("EDINET_API_KEY") or None
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self._transport: HttpTransport = transport or UrllibTransport()

    # -- public API ------------------------------------------------------------

    def list_documents(self, date: str) -> DocumentListResult:
        """Return the EDINET document list for a submission date (``YYYY-MM-DD``).

        Faithful: returns what EDINET reports, with no filtering or selection.
        """
        if not _DATE_RE.match(date):
            raise ValueError(f"date must be YYYY-MM-DD, got {date!r}")
        response = self._request(
            "/documents.json",
            {"date": date, "type": _LIST_TYPE},
            context=f"document list for {date}",
        )
        payload = self._decode_json(response, context=f"document list for {date}")
        self._raise_for_body_error(payload, context=f"document list for {date}")

        results = payload.get("results")
        if not isinstance(results, list):
            raise EdinetResponseError(
                f"EDINET document list for {date} has no results array"
            )
        metadata = payload.get("metadata") or {}
        resultset = metadata.get("resultset") or {}
        count = resultset.get("count")
        return DocumentListResult(
            date=date,
            documents=[_document_from_result(item) for item in results],
            retrieved_at=_utc_now_iso(),
            api_version=API_VERSION,
            result_count=int(count) if isinstance(count, int) else None,
            process_datetime=metadata.get("processDateTime"),
        )

    def download_document(self, document_id: str) -> DocumentDownload:
        """Return the raw submission ZIP for a ``docID``, exactly as received."""
        if not _DOC_ID_RE.match(document_id or ""):
            raise ValueError(f"document_id must be alphanumeric, got {document_id!r}")
        context = f"document download for {document_id}"
        response = self._request(
            f"/documents/{document_id}", {"type": _PACKAGE_TYPE}, context=context
        )
        content_type = response.content_type().split(";")[0].strip().lower()
        if content_type == "application/json":
            payload = self._decode_json(response, context=context)
            self._raise_for_body_error(payload, context=context, document_id=document_id)
            raise EdinetResponseError(
                f"EDINET returned JSON instead of a package for {context}"
            )
        if content_type not in ("application/octet-stream", "application/zip"):
            raise EdinetResponseError(
                f"EDINET returned unexpected content type {content_type!r} for {context}"
            )
        if not response.body.startswith(_ZIP_MAGIC):
            raise EdinetResponseError(
                f"EDINET response body is not a ZIP archive for {context}"
            )
        return DocumentDownload(
            document_id=document_id,
            content=response.body,
            media_type="application/zip",
            retrieved_at=_utc_now_iso(),
            api_version=API_VERSION,
        )

    # -- internals ---------------------------------------------------------------

    def _request(
        self, path: str, params: Mapping[str, str], *, context: str
    ) -> HttpResponse:
        if not self._api_key:
            raise ConfigurationError(
                "EDINET API key is not configured (pass api_key or set EDINET_API_KEY)"
            )
        # The key travels only in this header — never in the URL.
        url = f"{self.api_base}{path}?{urllib.parse.urlencode(dict(params))}"
        headers = {
            "Ocp-Apim-Subscription-Key": self._api_key,
            "User-Agent": "edinet-replay",
        }

        attempts = self.max_retries + 1
        last_status: int | None = None
        for attempt in range(attempts):
            try:
                response = self._transport.request(
                    url, headers=headers, timeout=self.timeout
                )
            except (TimeoutError, OSError) as err:
                raise EdinetTransportError(
                    f"EDINET request failed for {context}: {type(err).__name__}"
                ) from None
            if response.status == 200:
                return response
            last_status = response.status
            if response.status == 429 or response.status >= 500:
                if attempt < attempts - 1:
                    time.sleep(self.retry_backoff * (2**attempt))
                    continue
                if response.status == 429:
                    raise EdinetRateLimitError(
                        f"EDINET rate limit persisted for {context} "
                        f"(HTTP 429 after {attempts} attempts)"
                    )
                raise EdinetTransportError(
                    f"EDINET request failed for {context} "
                    f"(HTTP {response.status} after {attempts} attempts)"
                )
            raise EdinetTransportError(
                f"EDINET request failed for {context} (HTTP {response.status})"
            )
        raise EdinetTransportError(  # pragma: no cover — loop always returns/raises
            f"EDINET request failed for {context} (HTTP {last_status})"
        )

    @staticmethod
    def _decode_json(response: HttpResponse, *, context: str) -> Mapping[str, object]:
        content_type = response.content_type().split(";")[0].strip().lower()
        if content_type != "application/json":
            raise EdinetResponseError(
                f"EDINET returned unexpected content type {content_type!r} for {context}"
            )
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise EdinetResponseError(
                f"EDINET returned undecodable JSON for {context}"
            ) from None
        if not isinstance(payload, dict):
            raise EdinetResponseError(
                f"EDINET returned a non-object JSON payload for {context}"
            )
        return payload

    @staticmethod
    def _raise_for_body_error(
        payload: Mapping[str, object], *, context: str, document_id: str | None = None
    ) -> None:
        """Translate EDINET's body-level statuses (HTTP is 200 either way)."""
        # Subscription-key rejection: {"StatusCode": 401, "message": ...}
        if payload.get("StatusCode") == 401:
            raise EdinetAuthenticationError(
                f"EDINET rejected the subscription key for {context}"
            )
        metadata = payload.get("metadata")
        if isinstance(metadata, dict):
            status = str(metadata.get("status", ""))
            if status == "404" and document_id is not None:
                raise DocumentNotFoundError(
                    f"EDINET has no document {document_id}"
                )
            if status and status != "200":
                message = metadata.get("message", "")
                raise EdinetResponseError(
                    f"EDINET reported status {status} ({message}) for {context}"
                )
