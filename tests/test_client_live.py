"""Optional live EDINET API integration tests.

Skipped unless BOTH are set (never runs in CI, which has no key):

    EDINET_API_KEY=...              the real subscription key
    EDINET_REPLAY_LIVE_API_TESTS=1  explicit opt-in to hit the live API

Run locally: EDINET_REPLAY_LIVE_API_TESTS=1 pytest tests/test_client_live.py -v
"""
from __future__ import annotations

import os

import pytest

from edinet_replay.client import EdinetClient
from edinet_replay.exceptions import EdinetAuthenticationError

pytestmark = pytest.mark.skipif(
    not (os.environ.get("EDINET_API_KEY") and os.environ.get("EDINET_REPLAY_LIVE_API_TESTS")),
    reason="live API tests need EDINET_API_KEY and EDINET_REPLAY_LIVE_API_TESTS=1",
)

# A stable past business day and a known docID (E04236 annual report, also the
# JP GAAP golden input).
LIST_DATE = "2025-06-27"
KNOWN_DOC_ID = "S100W1NC"


def test_live_list_documents():
    result = EdinetClient().list_documents(LIST_DATE)
    assert result.result_count and result.result_count > 0
    assert any(doc.is_amendment for doc in result.documents)
    assert all(doc.document_id for doc in result.documents)


def test_live_download_document():
    result = EdinetClient().download_document(KNOWN_DOC_ID)
    assert result.content.startswith(b"PK")
    assert len(result.content) > 100_000


def test_live_invalid_key_is_body_level_401():
    client = EdinetClient(api_key="0" * 32)
    with pytest.raises(EdinetAuthenticationError):
        client.list_documents(LIST_DATE)
