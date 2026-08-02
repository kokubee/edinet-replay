"""Golden regression for E01532 (US GAAP): faithful projection is byte-stable
across independent runs and matches the committed canonical hash.

Skipped unless the local taxonomy zip and the E01532 filing are present.
"""
import gzip
import hashlib
import json
import os
import pathlib

import pytest

from edinet_replay import canonical, extract, schemas, taxonomy

pytest.importorskip("arelle")

HOME = pathlib.Path.home()
TAXO_ZIP = HOME / ".cache/edinet-replay/taxonomies/edinet-fsa-2024-11-01/1c_Taxonomy.zip"
FILINGS = pathlib.Path(os.environ.get("EDINET_REPLAY_TEST_FILINGS", ""))
XBRL = (
    FILINGS
    / "E01532/S100VXAI/XBRL/PublicDoc/jpcrp030000-asr-001_E01532-000_2025-03-31_01_2025-06-16.xbrl"
)
GOLD_DIR = pathlib.Path(__file__).resolve().parent / "golden"
GOLD_META = json.loads((GOLD_DIR / "E01532-S100VXAI.json").read_text(encoding="utf-8"))
GOLD_GZ = GOLD_DIR / "E01532-S100VXAI.canonical.json.gz"

_needs_assets = pytest.mark.skipif(
    not (TAXO_ZIP.exists() and XBRL.exists()),
    reason="requires local EDINET taxonomy and the E01532 filing",
)


def _generate(tmp) -> tuple[dict, bytes]:
    ref = taxonomy.register(
        TAXO_ZIP,
        identifier="edinet-fsa-2024-11-01",
        version="2025",
        registry_dir=tmp / "reg",
    )
    extracted = tmp / "reg" / "edinet-fsa-2024-11-01" / "2025" / "extracted"
    cfg = taxonomy.seed_arelle_web_cache(
        extracted,
        taxonomy_id=ref.identifier,
        content_sha256=ref.content_sha256,
        cache_root=tmp / "wc",
    )
    _, model, missing = extract.load_offline(str(XBRL), cfg)
    assert missing == []
    filing = extract.project_faithful_filing(
        model,
        document_id="S100VXAI",
        package_path="XBRL/PublicDoc/" + XBRL.name,
    )
    return filing, canonical.canonicalize(filing)


def test_meta_declares_us_gaap():
    assert GOLD_META["accounting_standard"] == "US GAAP"
    assert GOLD_META["edinet_code"] == "E01532"
    assert GOLD_META["document_id"] == "S100VXAI"


def test_committed_golden_matches_its_metadata():
    """Always runs: the committed gzip decompresses to the recorded hash/size."""
    body = gzip.decompress(GOLD_GZ.read_bytes())
    assert hashlib.sha256(body).hexdigest() == GOLD_META["canonical_output_sha256"]
    assert len(body) == GOLD_META["canonical_output_size_bytes"]


@_needs_assets
def test_projection_matches_golden_hash(tmp_path):
    filing, body = _generate(tmp_path)
    schemas.validate(filing, schemas.FAITHFUL_FILING_SCHEMA)
    assert hashlib.sha256(body).hexdigest() == GOLD_META["canonical_output_sha256"]
    assert len(filing["facts"]) == GOLD_META["fact_count"]


@_needs_assets
def test_generated_bytes_equal_committed_golden(tmp_path):
    _, body = _generate(tmp_path)
    assert body == gzip.decompress(GOLD_GZ.read_bytes())


@_needs_assets
def test_two_independent_runs_are_byte_identical(tmp_path_factory):
    _, a = _generate(tmp_path_factory.mktemp("run_a"))
    _, b = _generate(tmp_path_factory.mktemp("run_b"))
    assert a == b
    assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest()
