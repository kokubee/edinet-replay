"""Cross-document semantic checks that JSON Schema alone cannot express.

JSON Schema cannot check referential integrity between maps, or the manifest <->
filing relationship. These checks do.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "minimal"

MANIFEST = json.loads((FIX / "extraction-manifest.json").read_text(encoding="utf-8"))
FILING = json.loads((FIX / "faithful-filing.json").read_text(encoding="utf-8"))


def test_selected_document_is_the_source_package() -> None:
    assert (
        MANIFEST["selection"]["selected_document_id"]
        == MANIFEST["source_package"]["document_id"]
    )


def test_selected_document_is_among_candidates() -> None:
    assert (
        MANIFEST["selection"]["selected_document_id"]
        in MANIFEST["selection"]["candidate_document_ids"]
    )


def test_filing_document_matches_manifest_source() -> None:
    assert FILING["filing"]["document_id"] == MANIFEST["source_package"]["document_id"]


def test_every_source_context_ref_resolves() -> None:
    for fid, fact in FILING["facts"].items():
        assert fact["source_context_ref"] in FILING["contexts"], fid


def test_every_source_unit_ref_resolves() -> None:
    for fid, fact in FILING["facts"].items():
        ref = fact.get("source_unit_ref")
        if ref is not None:
            assert ref in FILING["units"], fid


def test_a_fact_with_a_unit_ref_also_has_a_resolved_unit() -> None:
    for fid, fact in FILING["facts"].items():
        if fact.get("source_unit_ref"):
            assert "unit" in fact["dimensions"], fid


def test_footnote_relationships_resolve_on_both_ends() -> None:
    for rel in FILING.get("fact_footnote_relationships", []):
        assert rel["fact_id"] in FILING["facts"], rel
        assert rel["footnote_id"] in FILING["footnotes"], rel


def test_nil_and_value_are_consistent() -> None:
    for fid, fact in FILING["facts"].items():
        if fact["nil"]:
            assert fact["value"] is None, fid
        else:
            assert fact["value"] is not None, fid


def test_provenance_matches_fact_kind() -> None:
    for fid, fact in FILING["facts"].items():
        has_numeric = "numeric_provenance" in fact
        has_text = "text_provenance" in fact
        assert not (has_numeric and has_text), f"{fid}: both provenance blocks"
        if has_numeric:
            assert "unit" in fact["dimensions"], f"{fid}: numeric provenance without unit"
        if has_text:
            assert "unit" not in fact["dimensions"], f"{fid}: text provenance with unit"
