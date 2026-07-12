"""Integration test: faithful XBRL projection of E04236 (JP GAAP).

Loads the preferred .xbrl instance offline, projects it onto the faithful-filing
schema, builds the manifest, validates both, checks referential integrity, and
cross-checks the .xbrl fact set against the inline document set (count AND
signature). Skipped unless the local taxonomy zip and the E04236 package exist.
"""
import collections
import os
import pathlib
import xml.etree.ElementTree as ET

import pytest

from edinet_replay import extract, package, schemas, taxonomy
from edinet_replay.models import SelectionRecord

pytest.importorskip("arelle")
from arelle import Cntlr, Version  # noqa: E402

HOME = pathlib.Path.home()
TAXO_ZIP = HOME / ".cache/edinet-replay/taxonomies/edinet-fsa-2024-11-01/1c_Taxonomy.zip"
FILINGS = pathlib.Path(os.environ.get("EDINET_REPLAY_TEST_FILINGS", ""))
PKG = FILINGS / "E04236/S100W1NC"
RAW_ZIP = PKG.with_suffix(".zip")
PUBLIC_DOC = PKG / "XBRL" / "PublicDoc"
XBRL = PUBLIC_DOC / "jpcrp030000-asr-001_E04236-000_2025-03-31_01_2025-06-23.xbrl"

pytestmark = pytest.mark.skipif(
    not (TAXO_ZIP.exists() and XBRL.exists() and RAW_ZIP.exists()),
    reason="requires local EDINET taxonomy and the E04236 package",
)

_MANIFEST_NS = "{http://disclosure.edinet-fsa.go.jp/2013/manifest}"


def _sig(concept, ctxref, unitref, nil):
    # Structural signature: fact-set identity (concept + context + unit + nil).
    # Value is intentionally excluded — textBlock HTML serializes differently in
    # .xbrl vs inline form; value-level equality is deferred to the IXDS commit.
    return (concept, ctxref or "", unitref or "", bool(nil))


def _load(entry, cfg):
    cntlr = Cntlr.Cntlr(logFileName="logToBuffer")
    cntlr.webCache.cacheDir = cfg.web_cache_dir
    cntlr.webCache.workOffline = True
    return cntlr.modelManager.load(str(entry))


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("proj")
    src = package.store(RAW_ZIP.read_bytes(), document_id="S100W1NC", dest_dir=tmp / "pkg",
                        retrieved_at="2026-07-12T00:00:00Z")
    ref = taxonomy.register(TAXO_ZIP, identifier="edinet-fsa-2024-11-01", version="2025",
                            registry_dir=tmp / "registry")
    extracted = tmp / "registry" / "edinet-fsa-2024-11-01" / "2025" / "extracted"
    cfg = taxonomy.seed_arelle_web_cache(extracted, taxonomy_id=ref.identifier,
                                         content_sha256=ref.content_sha256, cache_root=tmp / "wc")
    model = _load(XBRL, cfg)
    pkg_path = "XBRL/PublicDoc/" + XBRL.name
    filing = extract.project_faithful_filing(model, document_id="S100W1NC", package_path=pkg_path)

    # cross-check against the inline document set (structural: fact-set identity)
    manifest_root = ET.parse(PUBLIC_DOC / "manifest_PublicDoc.xml").getroot()
    order = [e.text.strip() for e in manifest_root.iter(_MANIFEST_NS + "ixbrl")]
    xbrl_sigs = collections.Counter(
        _sig(
            f.qname.clarkNotation,
            f.context.id if f.context is not None else None,
            f.unit.id if f.unit is not None else None,
            f.isNil,
        )
        for f in model.facts
    )
    ixbrl_sigs = collections.Counter()
    ixbrl_total = 0
    for name in order:
        m = _load(PUBLIC_DOC / name, cfg)
        for f in m.facts:
            ixbrl_total += 1
            key = _sig(f.qname.clarkNotation, f.get("contextRef"), f.get("unitRef"), f.isNil)
            ixbrl_sigs[key] += 1

    crosscheck = {
        "ixbrl_document_count": len(order),
        "xbrl_fact_count": len(model.facts),
        "ixbrl_fact_count": ixbrl_total,
        "counts_match": len(model.facts) == ixbrl_total,
        "structural_signatures_match": xbrl_sigs == ixbrl_sigs,
    }
    selection = SelectionRecord(
        selected_by="explicit_document", selector_version="0",
        selected_document_id="S100W1NC", candidate_document_ids=["S100W1NC"],
    )
    manifest = extract.build_manifest(
        src, ref, selection, arelle_version=Version.__version__, extractor_version="0.1.0",
        extraction_source={
            "kind": "xbrl-instance", "package_path": pkg_path,
            "selected_from_manifest": True, "preferred_filename": True,
            "ixbrl_crosscheck": crosscheck,
        },
        generated_at="2026-07-12T00:00:00Z",
    )
    return {"filing": filing, "manifest": manifest, "crosscheck": crosscheck}


def test_faithful_filing_is_schema_valid(built):
    schemas.validate(built["filing"], schemas.FAITHFUL_FILING_SCHEMA)


def test_manifest_is_schema_valid(built):
    schemas.validate(built["manifest"], schemas.MANIFEST_SCHEMA)


def test_capabilities_declare_xbrl_only(built):
    caps = built["filing"]["provenance_capabilities"]
    assert caps == {"resolved_xbrl": True, "ixbrl_lexical": False, "ixbrl_presentation": False}


def test_no_ixbrl_provenance_fields_are_present(built):
    for f in built["filing"]["facts"].values():
        assert "numeric_provenance" not in f  # omitted, not null, in xbrl-instance mode
        assert "text_provenance" not in f


def test_referential_integrity(built):
    f = built["filing"]
    for fid, fact in f["facts"].items():
        assert fact["source_context_ref"] in f["contexts"], fid
        if fact.get("source_unit_ref"):
            assert fact["source_unit_ref"] in f["units"], fid
        assert (fact["value"] is None) == fact["nil"]
    for rel in f.get("fact_footnote_relationships", []):
        assert rel["fact_id"] in f["facts"]
        assert rel["footnote_id"] in f.get("footnotes", {})


def test_crosscheck_counts_match(built):
    cc = built["crosscheck"]
    assert cc["counts_match"] is True
    assert cc["xbrl_fact_count"] == cc["ixbrl_fact_count"] == len(built["filing"]["facts"])


def test_crosscheck_structural_signatures_match(built):
    assert built["crosscheck"]["structural_signatures_match"] is True
