"""Tests for taxonomy registry, catalog filtering, and document selection."""
import io
import zipfile
from datetime import datetime

import pytest

from edinet_replay import catalog, selectors, taxonomy
from edinet_replay.exceptions import NoCandidatesError, TaxonomyConflictError
from edinet_replay.models import DocumentMetadata


def _zip(files, compression=zipfile.ZIP_DEFLATED):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression) as zf:
        for name, data in files:
            zf.writestr(name, data)
    return buf.getvalue()


# --- taxonomy ----------------------------------------------------------------

def _write(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_taxonomy_register_and_verify(tmp_path):
    pkg_path = _write(tmp_path, "tax.zip", _zip([("core.xsd", b"<schema/>")]))
    reg = tmp_path / "registry"
    ref = taxonomy.register(
        pkg_path, identifier="edinet-taxonomy-2026", version="2026-02-28", registry_dir=reg
    )
    assert len(ref.raw_sha256) == 64 and len(ref.content_sha256) == 64
    assert taxonomy.verify(ref, pkg_path) is True


def test_taxonomy_reregister_same_content_is_idempotent(tmp_path):
    pkg_path = _write(tmp_path, "tax.zip", _zip([("core.xsd", b"<schema/>")]))
    reg = tmp_path / "registry"
    a = taxonomy.register(pkg_path, identifier="t", version="v1", registry_dir=reg)
    b = taxonomy.register(pkg_path, identifier="t", version="v1", registry_dir=reg)
    assert a.content_sha256 == b.content_sha256


def test_taxonomy_conflicting_version_is_rejected(tmp_path):
    reg = tmp_path / "registry"
    p1 = _write(tmp_path, "a.zip", _zip([("core.xsd", b"<schema>one</schema>")]))
    p2 = _write(tmp_path, "b.zip", _zip([("core.xsd", b"<schema>two</schema>")]))
    taxonomy.register(p1, identifier="t", version="v1", registry_dir=reg)
    with pytest.raises(TaxonomyConflictError):
        taxonomy.register(p2, identifier="t", version="v1", registry_dir=reg)


# --- catalog -----------------------------------------------------------------

DOCS = [
    DocumentMetadata(
        "S100AAA1", edinet_code="E001", doc_type_code="120",
        submit_datetime="2026-06-25T10:00:00",
    ),
    DocumentMetadata(
        "S100AAA2", edinet_code="E001", doc_type_code="130",
        submit_datetime="2026-06-26T09:00:00", is_amendment=True,
    ),
    DocumentMetadata(
        "S100BBB1", edinet_code="E002", doc_type_code="120",
        submit_datetime="2026-06-24T12:00:00",
    ),
]


def test_filter_is_order_independent():
    forward = catalog.filter_documents(DOCS, edinet_code="E001")
    backward = catalog.filter_documents(list(reversed(DOCS)), edinet_code="E001")
    assert [d.document_id for d in forward] == [d.document_id for d in backward]


def test_filter_returns_ascending_order():
    out = catalog.filter_documents(DOCS)
    assert [d.document_id for d in out] == ["S100BBB1", "S100AAA1", "S100AAA2"]


def test_filter_by_type_and_amendments():
    out = catalog.filter_documents(DOCS, doc_type_codes={"120"}, include_amendments=False)
    assert [d.document_id for d in out] == ["S100BBB1", "S100AAA1"]


def test_filter_by_date_range():
    out = catalog.filter_documents(DOCS, submitted_from=datetime(2026, 6, 25))
    assert [d.document_id for d in out] == ["S100AAA1", "S100AAA2"]


# --- selectors ---------------------------------------------------------------

def test_latest_original_excludes_amendments_and_records_candidates():
    rec = selectors.latest_original_filing(DOCS, parameters={"edinet_code": "E001"})
    assert rec.selected_document_id == "S100AAA1"  # AAA2 is an amendment
    assert rec.candidate_document_ids == ["S100AAA1", "S100AAA2", "S100BBB1"]
    assert rec.selected_by == "latest_original_filing"
    assert rec.selector_version == "1.0.0"
    assert rec.parameters == {"edinet_code": "E001"}


def test_latest_original_tie_breaks_on_document_id():
    tied = [
        DocumentMetadata("S100ZZZ2", submit_datetime="2026-06-25T10:00:00"),
        DocumentMetadata("S100ZZZ9", submit_datetime="2026-06-25T10:00:00"),
    ]
    rec = selectors.latest_original_filing(tied)
    assert rec.selected_document_id == "S100ZZZ9"


def test_latest_original_no_candidates_raises():
    only_amendments = [DocumentMetadata("S100AMD1", is_amendment=True)]
    with pytest.raises(NoCandidatesError):
        selectors.latest_original_filing(only_amendments)
