"""EdinetClient unit tests — fake transport only, no live API, no key needed.

The fixtures under ``tests/fixtures/edinet_api/`` are sanitized captures of real
EDINET v2 responses (public disclosure data; no subscription key). The central
EDINET quirk under test: **every error comes back as HTTP 200**, with the real
status in the body.
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from edinet_replay.client import DEFAULT_API_BASE, EdinetClient, HttpResponse
from edinet_replay.exceptions import (
    ConfigurationError,
    DocumentNotFoundError,
    EdinetAuthenticationError,
    EdinetRateLimitError,
    EdinetResponseError,
    EdinetTransportError,
)

FIXTURES = Path(__file__).parent / "fixtures" / "edinet_api"
TEST_KEY = "unit-test-key-not-a-real-secret"

JSON_HEADERS = {"Content-Type": "application/json; charset=utf-8"}
ZIP_HEADERS = {"Content-Type": "application/octet-stream"}


def _fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("XBRL/PublicDoc/example.xbrl", "<xbrl/>")
    return buf.getvalue()


class FakeTransport:
    """Returns queued responses in order and records every request."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, url, *, headers, timeout):
        self.requests.append({"url": url, "headers": dict(headers), "timeout": timeout})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _client(responses, **kwargs):
    transport = FakeTransport(responses)
    kwargs.setdefault("api_key", TEST_KEY)
    kwargs.setdefault("retry_backoff", 0.0)
    return EdinetClient(transport=transport, **kwargs), transport


# --- list_documents ---------------------------------------------------------------


def test_list_documents_success_maps_metadata():
    client, transport = _client(
        [HttpResponse(200, JSON_HEADERS, _fixture_bytes("documents_success.json"))]
    )
    result = client.list_documents("2025-06-27")

    assert result.date == "2025-06-27"
    assert result.api_version == "v2"
    assert result.result_count == 2
    assert result.process_datetime == "2026-07-12 00:00"
    assert result.retrieved_at.endswith("Z")

    normal, amendment = result.documents
    assert normal.document_id == "S100W830"
    assert normal.edinet_code == "E40399"
    assert normal.submitter_name == "株式会社ＴａｌｅｎｔＸ"
    assert normal.doc_type_code == "180"
    assert normal.is_amendment is False
    assert normal.parent_document_id is None

    assert amendment.document_id == "S100W81U"
    assert amendment.is_amendment is True
    assert amendment.parent_document_id == "S100W3X3"

    # The key travels in the header, never in the URL.
    request = transport.requests[0]
    assert request["headers"]["Ocp-Apim-Subscription-Key"] == TEST_KEY
    assert TEST_KEY not in request["url"]
    assert request["url"].startswith(DEFAULT_API_BASE + "/documents.json?")
    assert "type=2" in request["url"]


def test_http_200_with_body_401_is_authentication_error():
    client, _ = _client([HttpResponse(200, JSON_HEADERS, _fixture_bytes("auth_error.json"))])
    with pytest.raises(EdinetAuthenticationError) as excinfo:
        client.list_documents("2025-06-27")
    assert TEST_KEY not in str(excinfo.value)


def test_http_200_with_body_400_is_response_error():
    client, _ = _client([HttpResponse(200, JSON_HEADERS, _fixture_bytes("bad_request.json"))])
    with pytest.raises(EdinetResponseError, match="status 400"):
        client.list_documents("2025-06-27")


def test_http_500_retries_then_transport_error():
    client, transport = _client(
        [HttpResponse(500, {}, b"") for _ in range(4)], max_retries=3
    )
    with pytest.raises(EdinetTransportError, match="HTTP 500 after 4 attempts"):
        client.list_documents("2025-06-27")
    assert len(transport.requests) == 4


def test_http_429_retries_then_rate_limit_error():
    client, transport = _client([HttpResponse(429, {}, b"") for _ in range(3)], max_retries=2)
    with pytest.raises(EdinetRateLimitError):
        client.list_documents("2025-06-27")
    assert len(transport.requests) == 3


def test_http_429_then_success_recovers():
    client, transport = _client(
        [
            HttpResponse(429, {}, b""),
            HttpResponse(200, JSON_HEADERS, _fixture_bytes("documents_success.json")),
        ]
    )
    assert len(client.list_documents("2025-06-27").documents) == 2
    assert len(transport.requests) == 2


def test_http_400_is_not_retried():
    client, transport = _client([HttpResponse(400, {}, b"")], max_retries=3)
    with pytest.raises(EdinetTransportError, match="HTTP 400"):
        client.list_documents("2025-06-27")
    assert len(transport.requests) == 1


def test_timeout_is_transport_error_without_retry():
    client, transport = _client([TimeoutError("timed out")], max_retries=3)
    with pytest.raises(EdinetTransportError, match="TimeoutError"):
        client.list_documents("2025-06-27")
    assert len(transport.requests) == 1


def test_unexpected_content_type_is_response_error():
    client, _ = _client([HttpResponse(200, {"Content-Type": "text/html"}, b"<html/>")])
    with pytest.raises(EdinetResponseError, match="content type"):
        client.list_documents("2025-06-27")


def test_undecodable_json_is_response_error():
    client, _ = _client([HttpResponse(200, JSON_HEADERS, b"{not json")])
    with pytest.raises(EdinetResponseError, match="undecodable"):
        client.list_documents("2025-06-27")


def test_missing_results_array_is_response_error():
    body = json.dumps({"metadata": {"status": "200"}}).encode()
    client, _ = _client([HttpResponse(200, JSON_HEADERS, body)])
    with pytest.raises(EdinetResponseError, match="no results array"):
        client.list_documents("2025-06-27")


def test_invalid_date_is_rejected_locally():
    client, transport = _client([])
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        client.list_documents("2025/06/27")
    assert transport.requests == []


def test_missing_api_key_is_configuration_error(monkeypatch):
    monkeypatch.delenv("EDINET_API_KEY", raising=False)
    client = EdinetClient(transport=FakeTransport([]))
    with pytest.raises(ConfigurationError, match="EDINET_API_KEY"):
        client.list_documents("2025-06-27")


# --- download_document ------------------------------------------------------------


def test_download_document_success_returns_zip_bytes():
    payload = _zip_bytes()
    client, transport = _client([HttpResponse(200, ZIP_HEADERS, payload)])
    result = client.download_document("S100W1NC")

    assert result.content == payload
    assert result.document_id == "S100W1NC"
    assert result.media_type == "application/zip"
    assert result.api_version == "v2"
    assert result.retrieved_at.endswith("Z")

    request = transport.requests[0]
    assert request["url"].startswith(DEFAULT_API_BASE + "/documents/S100W1NC?")
    assert "type=1" in request["url"]
    assert TEST_KEY not in request["url"]


def test_download_json_404_is_document_not_found():
    client, _ = _client([HttpResponse(200, JSON_HEADERS, _fixture_bytes("not_found.json"))])
    with pytest.raises(DocumentNotFoundError, match="S999ZZZZ"):
        client.download_document("S999ZZZZ")


def test_download_json_401_is_authentication_error():
    client, _ = _client([HttpResponse(200, JSON_HEADERS, _fixture_bytes("auth_error.json"))])
    with pytest.raises(EdinetAuthenticationError):
        client.download_document("S100W1NC")


def test_download_unexpected_json_is_response_error():
    body = json.dumps({"metadata": {"status": "200"}}).encode()
    client, _ = _client([HttpResponse(200, JSON_HEADERS, body)])
    with pytest.raises(EdinetResponseError, match="JSON instead of a package"):
        client.download_document("S100W1NC")


def test_download_non_zip_body_is_response_error():
    client, _ = _client([HttpResponse(200, ZIP_HEADERS, b"this is not a zip")])
    with pytest.raises(EdinetResponseError, match="not a ZIP"):
        client.download_document("S100W1NC")


def test_download_invalid_document_id_rejected_locally():
    client, transport = _client([])
    with pytest.raises(ValueError, match="alphanumeric"):
        client.download_document("../etc/passwd")
    assert transport.requests == []


# --- key hygiene -------------------------------------------------------------------


def test_api_key_never_appears_in_exception_messages():
    scenarios = [
        HttpResponse(200, JSON_HEADERS, _fixture_bytes("auth_error.json")),
        HttpResponse(500, {}, b""),
        HttpResponse(200, {"Content-Type": "text/html"}, b""),
        TimeoutError("timed out"),
    ]
    for scenario in scenarios:
        client, _ = _client([scenario] * 5)
        with pytest.raises(Exception) as excinfo:
            client.list_documents("2025-06-27")
        message = str(excinfo.value)
        assert TEST_KEY not in message
        assert "https://" not in message
