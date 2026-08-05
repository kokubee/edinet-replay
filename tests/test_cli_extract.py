"""CLI ``extract`` tests — usage guards (no Arelle) + end-to-end when assets exist."""
from __future__ import annotations

import json
import os
import pathlib
import shutil

import pytest

from edinet_replay import cli, schemas
from edinet_replay.exceptions import ConfigurationError

HOME = pathlib.Path.home()
TAXO_ID = "edinet-fsa-2024-11-01"
TAXO_ZIP = HOME / ".cache/edinet-replay/taxonomies" / TAXO_ID / "1c_Taxonomy.zip"
FILINGS = pathlib.Path(os.environ.get("EDINET_REPLAY_TEST_FILINGS", ""))
RAW_ZIP = FILINGS / "E04236" / "S100W1NC.zip"
ROOT = pathlib.Path(__file__).resolve().parents[1]

_needs_assets = pytest.mark.skipif(
    not (TAXO_ZIP.exists() and RAW_ZIP.exists()),
    reason="requires local EDINET taxonomy and the E04236 package ZIP",
)


def test_cli_extract_requires_taxonomy_and_output(capsys):
    with pytest.raises(SystemExit):
        cli.main(["extract", "pkg.zip"])
    err = capsys.readouterr().err
    assert "--taxonomy" in err or "required" in err.lower()


def test_cli_extract_missing_package_reports_error(tmp_path, capsys):
    missing = tmp_path / "nope.zip"
    assert (
        cli.main(
            [
                "extract",
                str(missing),
                "--taxonomy",
                TAXO_ID,
                "--output-dir",
                str(tmp_path / "out"),
                "--document-id",
                "S100W1NC",
            ]
        )
        == 1
    )
    assert "error" in capsys.readouterr().err


def test_extract_package_requires_document_id(tmp_path):
    import io
    import zipfile

    from edinet_replay import extract

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("XBRL/PublicDoc/a.xbrl", b"<xbrl/>")
    zpath = tmp_path / "loose.zip"
    zpath.write_bytes(buf.getvalue())

    with pytest.raises(ConfigurationError, match="document_id"):
        extract.extract_package(
            zpath,
            taxonomy_identifier=TAXO_ID,
            pins_dir=ROOT / "taxonomies",
            registry_dir=tmp_path / "reg",
            cache_root=tmp_path / "wc",
        )


def test_extract_package_requires_acquisition_or_verified_retrieval_time(tmp_path):
    import io
    import zipfile

    from edinet_replay import extract

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("XBRL/PublicDoc/a.xbrl", b"<xbrl/>")
    zpath = tmp_path / "loose.zip"
    zpath.write_bytes(buf.getvalue())

    with pytest.raises(ConfigurationError, match="no acquisition record"):
        extract.extract_package(
            zpath,
            taxonomy_identifier=TAXO_ID,
            document_id="S100W1NC",
            pins_dir=ROOT / "taxonomies",
            registry_dir=tmp_path / "reg",
            cache_root=tmp_path / "wc",
        )


@_needs_assets
def test_cli_extract_e04236_end_to_end(tmp_path, capsys):
    store = tmp_path / "store"
    # Place under store layout so document_id is inferred.
    dest = store / "packages" / "S100W1NC"
    dest.mkdir(parents=True)
    raw = RAW_ZIP.read_bytes()
    from edinet_replay import package
    from edinet_replay.hashing import sha256_bytes
    from edinet_replay.models import SelectionRecord

    zpath = dest / f"{sha256_bytes(raw)}.zip"
    shutil.copyfile(RAW_ZIP, zpath)
    source = package.source_package_from_path(
        zpath, document_id="S100W1NC", retrieved_at="2025-06-27T00:00:00Z"
    )
    package.write_acquisition_record(
        source,
        api_version="v2",
        selection=SelectionRecord(
            selected_by="explicit_document",
            selector_version="0",
            selected_document_id="S100W1NC",
            candidate_document_ids=["S100W1NC"],
        ),
    )

    out = tmp_path / "out"
    rc = cli.main(
        [
            "extract",
            str(zpath),
            "--taxonomy",
            TAXO_ID,
            "--output-dir",
            str(out),
            "--taxonomy-zip",
            str(TAXO_ZIP),
            "--pins-dir",
            str(ROOT / "taxonomies"),
            "--registry-dir",
            str(tmp_path / "reg"),
            "--cache-root",
            str(tmp_path / "wc"),
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["document_id"] == "S100W1NC"
    assert payload["filing"]["fact_count"] == 2590
    assert payload["extraction_source"]["preferred_filename"] is True

    filing_path = pathlib.Path(payload["filing"]["path"])
    manifest_path = pathlib.Path(payload["manifest"]["path"])
    assert filing_path.is_file() and manifest_path.is_file()

    filing = json.loads(filing_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    schemas.validate(filing, schemas.FAITHFUL_FILING_SCHEMA)
    schemas.validate(manifest, schemas.MANIFEST_SCHEMA)
    assert manifest["source_package"]["retrieved_at"] == "2025-06-27T00:00:00Z"

    assert cli.main(["validate", "filing", str(filing_path)]) == 0
    assert cli.main(["validate", "manifest", str(manifest_path)]) == 0
