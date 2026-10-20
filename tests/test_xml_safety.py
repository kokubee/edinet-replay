"""Pre-Arelle XML safety checks: DTDs and external entities are refused."""
from __future__ import annotations

import pytest

pytest.importorskip("lxml")

from edinet_replay import extract  # noqa: E402
from edinet_replay.exceptions import ExtractionError  # noqa: E402


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_plain_xbrl_is_allowed(tmp_path):
    path = _write(
        tmp_path,
        "ok.xbrl",
        """<?xml version="1.0" encoding="utf-8"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance"/>
""",
    )
    extract.reject_unsafe_xml([path])


def test_doctype_with_external_entity_is_rejected(tmp_path):
    path = _write(
        tmp_path,
        "xxe.xbrl",
        """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE xbrl [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<xbrl xmlns="http://www.xbrl.org/2003/instance">&xxe;</xbrl>
""",
    )
    with pytest.raises(ExtractionError, match="DOCTYPE"):
        extract.reject_unsafe_xml([path])


def test_doctype_with_external_dtd_is_rejected_without_network(tmp_path):
    path = _write(
        tmp_path,
        "external-dtd.xbrl",
        """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE xbrl SYSTEM "http://example.invalid/xbrl.dtd">
<xbrl xmlns="http://www.xbrl.org/2003/instance"/>
""",
    )
    with pytest.raises(ExtractionError, match="DOCTYPE"):
        extract.reject_unsafe_xml([path])


def test_package_scan_covers_nested_xml_and_linkbases(tmp_path):
    nested = tmp_path / "XBRL" / "PublicDoc"
    nested.mkdir(parents=True)
    _write(
        nested,
        "manifest_PublicDoc.xml",
        """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns="http://disclosure.edinet-fsa.go.jp/2013/manifest"/>
""",
    )
    _write(
        nested,
        "evil.xml",
        """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE linkbase [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<linkbase xmlns="http://www.xbrl.org/2003/linkbase">&xxe;</linkbase>
""",
    )
    with pytest.raises(ExtractionError, match="DOCTYPE"):
        extract.reject_unsafe_package_xml(tmp_path)


def test_extract_package_rejects_dtd_before_arelle(tmp_path, monkeypatch):
    import io
    import zipfile

    pytest.importorskip("arelle")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "XBRL/PublicDoc/manifest_PublicDoc.xml",
            """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns="http://disclosure.edinet-fsa.go.jp/2013/manifest">
  <list><instance preferredFilename="evil.xbrl"/></list>
</manifest>
""",
        )
        zf.writestr(
            "XBRL/PublicDoc/evil.xbrl",
            """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE xbrl [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<xbrl xmlns="http://www.xbrl.org/2003/instance">&xxe;</xbrl>
""",
        )
    package = tmp_path / "evil.zip"
    package.write_bytes(buf.getvalue())

    monkeypatch.setattr(
        extract, "prepare_offline_taxonomy", lambda *args, **kwargs: (None, None, None)
    )

    def _must_not_load(*args, **kwargs):
        raise AssertionError("Arelle must not run on a DTD-bearing package")

    monkeypatch.setattr(extract, "load_offline", _must_not_load)

    with pytest.raises(ExtractionError, match="DOCTYPE"):
        extract.extract_package(
            package,
            taxonomy_identifier="unused",
            document_id="S100TEST",
            retrieved_at="2026-10-20T00:00:00Z",
        )
