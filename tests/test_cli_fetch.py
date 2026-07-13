"""CLI ``fetch`` tests — a stubbed client behind ``cli.main()``; no live API, no key.

Covers the three modes (explicit --document-id, --list-only, --select) plus the
"selection is never implicit" usage guards and the store-directory layout.
"""
from __future__ import annotations

import io
import json
import zipfile

import pytest

from edinet_replay import cli
from edinet_replay.exceptions import EdinetAuthenticationError
from edinet_replay.hashing import sha256_bytes
from edinet_replay.models import DocumentDownload, DocumentListResult, DocumentMetadata

LIST_DATE = "2025-06-27"

DOCS = [
    DocumentMetadata(
        document_id="S100AAA1",
        edinet_code="E00001",
        submitter_name="Original Co.",
        doc_type_code="120",
        submit_datetime="2025-06-27 09:00",
    ),
    DocumentMetadata(
        document_id="S100AAA2",
        edinet_code="E00001",
        submitter_name="Original Co.",
        doc_type_code="130",
        submit_datetime="2025-06-27 10:00",
        is_amendment=True,
        parent_document_id="S100AAA1",
    ),
    DocumentMetadata(
        document_id="S100BBB1",
        edinet_code="E00002",
        submitter_name="Other Co.",
        doc_type_code="180",
        submit_datetime="2025-06-27 11:00",
    ),
]


def _zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("XBRL/PublicDoc/example.xbrl", "<xbrl/>")
    return buf.getvalue()


ZIP_BYTES = _zip_bytes()


class StubClient:
    """Stands in for EdinetClient; records calls, returns canned results."""

    instances: list[StubClient] = []

    def __init__(self, *args, **kwargs):
        self.list_calls: list[str] = []
        self.download_calls: list[str] = []
        StubClient.instances.append(self)

    def list_documents(self, date):
        self.list_calls.append(date)
        return DocumentListResult(
            date=date,
            documents=list(DOCS),
            retrieved_at="2026-07-12T12:00:00Z",
            api_version="v2",
            result_count=len(DOCS),
            process_datetime="2026-07-12 00:00",
        )

    def download_document(self, document_id):
        self.download_calls.append(document_id)
        return DocumentDownload(
            document_id=document_id,
            content=ZIP_BYTES,
            media_type="application/zip",
            retrieved_at="2026-07-12T12:00:01Z",
            api_version="v2",
        )


@pytest.fixture()
def stub_client(monkeypatch):
    StubClient.instances = []
    monkeypatch.setattr(cli, "EdinetClient", StubClient)
    return StubClient


def _run(argv, capsys):
    code = cli.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# --- explicit --document-id ---------------------------------------------------------


def test_fetch_document_id_stores_package_and_prints_record(stub_client, tmp_path, capsys):
    code, out, _ = _run(
        ["fetch", "--document-id", "S100AAA1", "--store", str(tmp_path)], capsys
    )
    assert code == 0
    record = json.loads(out)
    assert record["document_id"] == "S100AAA1"
    assert record["package"]["raw_sha256"] == sha256_bytes(ZIP_BYTES)
    assert record["retrieval"] == {
        "retrieved_at": "2026-07-12T12:00:01Z",
        "api_version": "v2",
    }
    assert record["selection"]["selected_by"] == "explicit_document"
    assert record["selection"]["candidate_document_ids"] == ["S100AAA1"]

    stored = tmp_path / "packages" / "S100AAA1" / f"{sha256_bytes(ZIP_BYTES)}.zip"
    assert stored.is_file()
    assert stored.read_bytes() == ZIP_BYTES


def test_fetch_document_id_requires_store(stub_client, capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["fetch", "--document-id", "S100AAA1"])
    assert excinfo.value.code == 2


# --- --list-only --------------------------------------------------------------------


def test_fetch_list_only_prints_filtered_documents(stub_client, capsys):
    code, out, _ = _run(
        ["fetch", "--date", LIST_DATE, "--edinet-code", "E00001", "--list-only"], capsys
    )
    assert code == 0
    payload = json.loads(out)
    assert payload["date"] == LIST_DATE
    assert payload["api_version"] == "v2"
    assert payload["filter"]["edinet_code"] == "E00001"
    ids = [doc["document_id"] for doc in payload["documents"]]
    assert ids == ["S100AAA1", "S100AAA2"]
    assert stub_client.instances[0].download_calls == []


def test_fetch_list_only_doc_type_alias(stub_client, capsys):
    code, out, _ = _run(
        ["fetch", "--date", LIST_DATE, "--doc-type", "annual_securities_report", "--list-only"],
        capsys,
    )
    assert code == 0
    payload = json.loads(out)
    assert [doc["document_id"] for doc in payload["documents"]] == ["S100AAA1"]
    assert payload["filter"]["doc_type_codes"] == ["120"]


# --- --select ------------------------------------------------------------------------


def test_fetch_select_latest_original_downloads_original_not_amendment(
    stub_client, tmp_path, capsys
):
    code, out, _ = _run(
        [
            "fetch",
            "--date",
            LIST_DATE,
            "--edinet-code",
            "E00001",
            "--select",
            "latest-original-filing",
            "--store",
            str(tmp_path),
        ],
        capsys,
    )
    assert code == 0
    record = json.loads(out)
    # The amendment (S100AAA2, later submit time) is excluded by the selector.
    assert record["document_id"] == "S100AAA1"
    assert record["selection"]["selected_by"] == "latest_original_filing"
    assert record["selection"]["candidate_document_ids"] == ["S100AAA1", "S100AAA2"]
    assert record["selection"]["parameters"]["edinet_code"] == "E00001"
    assert stub_client.instances[0].download_calls == ["S100AAA1"]
    assert (tmp_path / "packages" / "S100AAA1").is_dir()


def test_fetch_select_with_only_amendments_is_error_exit_1(stub_client, tmp_path, capsys):
    code, _, err = _run(
        [
            "fetch",
            "--date",
            LIST_DATE,
            "--edinet-code",
            "E00001",
            "--doc-type",
            "130",
            "--select",
            "latest-original-filing",
            "--store",
            str(tmp_path),
        ],
        capsys,
    )
    assert code == 1
    assert "no original" in err


# --- selection is never implicit ------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["fetch", "--date", LIST_DATE],
        ["fetch", "--date", LIST_DATE, "--edinet-code", "E00001"],
        ["fetch"],
        ["fetch", "--document-id", "S100AAA1", "--date", LIST_DATE],
        ["fetch", "--date", LIST_DATE, "--select", "latest-original-filing", "--store", "x"],
        ["fetch", "--date", LIST_DATE, "--edinet-code", "E00001", "--select",
         "latest-original-filing"],
    ],
)
def test_fetch_usage_guards_exit_2(stub_client, argv):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(argv)
    assert excinfo.value.code == 2


# --- error surfaces --------------------------------------------------------------------


def test_fetch_client_error_is_exit_1(monkeypatch, capsys):
    class FailingClient(StubClient):
        def list_documents(self, date):
            raise EdinetAuthenticationError("EDINET rejected the subscription key")

    monkeypatch.setattr(cli, "EdinetClient", FailingClient)
    code, _, err = _run(["fetch", "--date", LIST_DATE, "--list-only"], capsys)
    assert code == 1
    assert "rejected the subscription key" in err


def test_fetch_without_key_is_exit_1(monkeypatch, capsys):
    monkeypatch.delenv("EDINET_API_KEY", raising=False)
    code, _, err = _run(["fetch", "--date", LIST_DATE, "--list-only"], capsys)
    assert code == 1
    assert "EDINET_API_KEY" in err