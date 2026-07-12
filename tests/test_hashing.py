"""Tests for the implemented content-hash algorithm."""
import io
import zipfile

import pytest

from edinet_replay import content_sha256_v1, zip_content_sha256_v1
from edinet_replay.hashing import normalize_entry_path, sha256_bytes

FILES = [
    ("XBRL/PublicDoc/a.xbrl", b"<xbrl>a</xbrl>"),
    ("XBRL/PublicDoc/b.htm", b"<html>b</html>"),
    ("manifest.xml", b"<manifest/>"),
]


def _zip(files, compression):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression) as zf:
        for name, data in files:
            zf.writestr(name, data)
    return buf.getvalue()


def test_content_hash_is_deterministic():
    assert content_sha256_v1(FILES) == content_sha256_v1(list(reversed(FILES)))


def test_content_hash_is_recompression_invariant(tmp_path):
    stored = tmp_path / "stored.zip"
    deflated = tmp_path / "deflated.zip"
    stored.write_bytes(_zip(FILES, zipfile.ZIP_STORED))
    deflated.write_bytes(_zip(FILES, zipfile.ZIP_DEFLATED))

    # raw bytes differ, but normalized content hash is identical
    assert sha256_bytes(stored.read_bytes()) != sha256_bytes(deflated.read_bytes())
    assert zip_content_sha256_v1(stored) == zip_content_sha256_v1(deflated)


def test_content_hash_changes_with_content(tmp_path):
    a = _zip(FILES, zipfile.ZIP_DEFLATED)
    b = _zip(FILES[:-1] + [("manifest.xml", b"<manifest changed=1/>")], zipfile.ZIP_DEFLATED)
    ap, bp = tmp_path / "a.zip", tmp_path / "b.zip"
    ap.write_bytes(a)
    bp.write_bytes(b)
    assert zip_content_sha256_v1(ap) != zip_content_sha256_v1(bp)


def test_normalize_strips_dot_slash_and_rejects_traversal():
    assert normalize_entry_path("./XBRL/a.xbrl") == "XBRL/a.xbrl"
    with pytest.raises(ValueError):
        normalize_entry_path("../secret")
