"""Integration test: E04236's DTS resolves offline from the isolated taxonomy
cache, with no network. Skipped unless the local taxonomy zip and the E04236
filing are present (they are large external assets, not committed)."""
import os
import pathlib

import pytest

from edinet_replay import taxonomy

pytest.importorskip("arelle")
from edinet_replay import extract  # noqa: E402

HOME = pathlib.Path.home()
TAXO_ZIP = HOME / ".cache/edinet-replay/taxonomies/edinet-fsa-2024-11-01/1c_Taxonomy.zip"
# Real filings live outside the repo; point EDINET_REPLAY_TEST_FILINGS at the
# directory holding {edinetCode}/{docID}/... (tests skip when unset/missing).
FILINGS = pathlib.Path(os.environ.get("EDINET_REPLAY_TEST_FILINGS", ""))
FILING = (
    FILINGS
    / "E04236/S100W1NC/XBRL/PublicDoc/jpcrp030000-asr-001_E04236-000_2025-03-31_01_2025-06-23.xbrl"
)

pytestmark = pytest.mark.skipif(
    not (TAXO_ZIP.exists() and FILING.exists()),
    reason="requires local EDINET taxonomy zip and the E04236 filing",
)


@pytest.fixture(scope="module")
def offline_config(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("taxo")
    ref = taxonomy.register(
        TAXO_ZIP, identifier="edinet-fsa-2024-11-01", version="2025", registry_dir=tmp / "registry"
    )
    extracted = tmp / "registry" / "edinet-fsa-2024-11-01" / "2025" / "extracted"
    return taxonomy.seed_arelle_web_cache(
        extracted,
        taxonomy_id=ref.identifier,
        content_sha256=ref.content_sha256,
        cache_root=tmp / "webcache",
    )


def test_config_is_offline(offline_config):
    assert offline_config.work_offline is True


def test_e04236_dts_resolves_offline_with_no_missing_refs(offline_config):
    _, model, missing = extract.load_offline(FILING, offline_config)
    assert model is not None
    assert missing == [], f"unresolved offline references: {missing}"
    assert len(model.facts) > 100  # DTS resolved -> full instance, not a stub


def test_required_core_urls_resolve_from_isolated_cache(offline_config):
    urls = [
        "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2024-11-01/jppfs_cor_2024-11-01.xsd",
        "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2024-11-01/jpcrp_cor_2024-11-01.xsd",
        "http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor_2013-08-31.xsd",
    ]
    res = taxonomy.verify_required_urls(offline_config, urls)
    assert res == {"resolved": 3, "missing": []}


def test_verify_rejects_foreign_host(offline_config):
    res = taxonomy.verify_required_urls(offline_config, ["https://evil.example/taxonomy/x.xsd"])
    assert res["resolved"] == 0 and res["missing"] == ["https://evil.example/taxonomy/x.xsd"]
