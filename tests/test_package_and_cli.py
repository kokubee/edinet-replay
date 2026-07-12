"""Smoke tests: the package imports, and the CLI validate/inspect/skeleton run."""
import importlib
import io
import pathlib
import zipfile

import pytest

from edinet_replay import __version__, cli

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "minimal"

MODULES = [
    "edinet_replay.client",
    "edinet_replay.catalog",
    "edinet_replay.selectors",
    "edinet_replay.package",
    "edinet_replay.taxonomy",
    "edinet_replay.extract",
    "edinet_replay.models",
    "edinet_replay.hashing",
    "edinet_replay.exceptions",
    "edinet_replay.schemas",
    "edinet_replay.cli",
]


def test_version():
    assert __version__ == "0.1.0a1"


@pytest.mark.parametrize("name", MODULES)
def test_all_modules_import(name):
    importlib.import_module(name)


def test_cli_no_command_prints_help_and_returns_zero(capsys):
    assert cli.main([]) == 0
    assert "edinet-replay" in capsys.readouterr().out


def test_cli_validate_manifest_fixture():
    assert cli.main(["validate", "manifest", str(FIX / "extraction-manifest.json")]) == 0


def test_cli_validate_filing_fixture():
    assert cli.main(["validate", "filing", str(FIX / "faithful-filing.json")]) == 0


def test_cli_validate_reports_bad_document(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    assert cli.main(["validate", "manifest", str(bad)]) == 1
    assert "error" in capsys.readouterr().err


def test_cli_inspect_reports_hashes(tmp_path, capsys):
    zpath = tmp_path / "pkg.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("XBRL/PublicDoc/a.xbrl", b"<xbrl/>")
    zpath.write_bytes(buf.getvalue())
    assert cli.main(["inspect", str(zpath)]) == 0
    out = capsys.readouterr().out
    assert "raw_sha256" in out and "content_sha256" in out


def test_cli_fetch_is_not_implemented():
    with pytest.raises(SystemExit):
        cli.main(["fetch", "--date", "2026-07-01"])


def test_cli_extract_is_not_implemented():
    with pytest.raises(SystemExit):
        cli.main(["extract", "some-package"])
