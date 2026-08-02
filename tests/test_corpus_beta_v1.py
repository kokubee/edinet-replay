"""β corpus catalog integrity — no Arelle, no local filings required.

Guarantees the public catalog, golden metadata, taxonomy pins, and committed
canonical gzip files stay aligned (JP GAAP / IFRS / US GAAP, one each).
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "corpus/beta-v1/catalog.json").read_text(encoding="utf-8"))

REQUIRED_META = {
    "accounting_standard",
    "edinet_code",
    "document_id",
    "submitter_name_en",
    "period_end",
    "taxonomy_identifier",
    "taxonomy_version",
    "source_raw_sha256",
    "source_content_sha256",
    "taxonomy_raw_sha256",
    "taxonomy_content_sha256",
    "canonical_output_sha256",
    "canonical_output_size_bytes",
    "fact_count",
    "canonicalization_profile",
    "preferred_xbrl",
}


def test_catalog_has_one_entry_per_standard():
    standards = [e["accounting_standard"] for e in CATALOG["entries"]]
    assert sorted(standards) == ["IFRS", "JP GAAP", "US GAAP"]
    assert len(CATALOG["entries"]) == 3


def test_catalog_ids_are_unique():
    ids = [e["id"] for e in CATALOG["entries"]]
    assert len(ids) == len(set(ids))


def test_each_entry_files_exist_and_meta_matches():
    for entry in CATALOG["entries"]:
        meta_path = ROOT / entry["golden_meta"]
        gz_path = ROOT / entry["golden_canonical_gz"]
        pin_path = ROOT / entry["taxonomy_pin"]
        assert meta_path.is_file(), entry["id"]
        assert gz_path.is_file(), entry["id"]
        assert pin_path.is_file(), entry["id"]

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        missing = REQUIRED_META - set(meta)
        assert not missing, f"{entry['id']}: missing {missing}"

        assert meta["accounting_standard"] == entry["accounting_standard"]
        assert meta["edinet_code"] == entry["edinet_code"]
        assert meta["document_id"] == entry["document_id"]
        assert meta["taxonomy_identifier"] == entry["taxonomy_identifier"]
        assert entry["id"] == f"{entry['edinet_code']}-{entry['document_id']}"

        pin = json.loads(pin_path.read_text(encoding="utf-8"))
        assert pin["identifier"] == entry["taxonomy_identifier"]
        assert pin["raw_sha256"] == meta["taxonomy_raw_sha256"]
        assert pin["content_sha256"] == meta["taxonomy_content_sha256"]

        body = gzip.decompress(gz_path.read_bytes())
        assert hashlib.sha256(body).hexdigest() == meta["canonical_output_sha256"]
        assert len(body) == meta["canonical_output_size_bytes"]
