"""Tests for package storage and safe extraction."""
import io
import zipfile

import pytest

from edinet_replay import package
from edinet_replay.exceptions import PackageConflictError, UnsafeArchiveError

GOOD = [
    ("XBRL/PublicDoc/a.xbrl", b"<xbrl>a</xbrl>"),
    ("XBRL/PublicDoc/b.htm", b"<html>b</html>"),
    ("manifest.xml", b"<manifest/>"),
]


def _zip(files, compression=zipfile.ZIP_DEFLATED, symlink=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression) as zf:
        for name, data in files:
            zf.writestr(name, data)
        if symlink is not None:
            name, target = symlink
            info = zipfile.ZipInfo(name)
            info.external_attr = (0o120777) << 16  # S_IFLNK
            zf.writestr(info, target)
    return buf.getvalue()


# --- store -------------------------------------------------------------------

def test_store_returns_dual_hashes_and_inventory(tmp_path):
    pkg = package.store(_zip(GOOD), document_id="S100ABCD", dest_dir=tmp_path)
    assert len(pkg.raw_sha256) == 64 and len(pkg.content_sha256) == 64
    assert {e.path for e in pkg.entries} == {n for n, _ in GOOD}
    assert pkg.document_id == "S100ABCD"


def test_store_is_idempotent(tmp_path):
    data = _zip(GOOD)
    a = package.store(data, document_id="S100ABCD", dest_dir=tmp_path)
    b = package.store(data, document_id="S100ABCD", dest_dir=tmp_path)
    assert a.path == b.path
    assert a.raw_sha256 == b.raw_sha256 and a.content_sha256 == b.content_sha256


def test_store_recompression_shares_content_hash_not_raw(tmp_path):
    stored = package.store(_zip(GOOD, zipfile.ZIP_STORED), document_id="D", dest_dir=tmp_path)
    deflated = package.store(_zip(GOOD, zipfile.ZIP_DEFLATED), document_id="D", dest_dir=tmp_path)
    assert stored.raw_sha256 != deflated.raw_sha256
    assert stored.content_sha256 == deflated.content_sha256
    assert stored.path != deflated.path  # content-addressed by raw hash


def test_store_rejects_conflicting_bytes(tmp_path):
    pkg = package.store(_zip(GOOD), document_id="S100ABCD", dest_dir=tmp_path)
    # corrupt the stored file, then re-store the same raw bytes -> conflict
    from pathlib import Path

    Path(pkg.path).write_bytes(b"corrupted")
    with pytest.raises(PackageConflictError):
        package.store(_zip(GOOD), document_id="S100ABCD", dest_dir=tmp_path)


# --- extract_safe ------------------------------------------------------------

def test_extract_safe_happy_path(tmp_path):
    zpath = tmp_path / "p.zip"
    zpath.write_bytes(_zip(GOOD))
    written = package.extract_safe(zpath, tmp_path / "out")
    assert len(written) == len(GOOD)
    assert (tmp_path / "out" / "XBRL" / "PublicDoc" / "a.xbrl").read_bytes() == b"<xbrl>a</xbrl>"


def test_extract_safe_rejects_traversal(tmp_path):
    zpath = tmp_path / "p.zip"
    zpath.write_bytes(_zip([("../evil.txt", b"x")]))
    with pytest.raises(UnsafeArchiveError):
        package.extract_safe(zpath, tmp_path / "out")


def test_extract_safe_rejects_absolute(tmp_path):
    zpath = tmp_path / "p.zip"
    zpath.write_bytes(_zip([("/etc/evil", b"x")]))
    with pytest.raises(UnsafeArchiveError):
        package.extract_safe(zpath, tmp_path / "out")


def test_extract_safe_rejects_symlink(tmp_path):
    zpath = tmp_path / "p.zip"
    zpath.write_bytes(_zip(GOOD, symlink=("link", "/etc/passwd")))
    with pytest.raises(UnsafeArchiveError):
        package.extract_safe(zpath, tmp_path / "out")


def test_extract_safe_enforces_max_entries(tmp_path):
    zpath = tmp_path / "p.zip"
    zpath.write_bytes(_zip(GOOD))
    with pytest.raises(UnsafeArchiveError):
        package.extract_safe(zpath, tmp_path / "out", max_entries=1)


def test_find_public_doc(tmp_path):
    zpath = tmp_path / "p.zip"
    zpath.write_bytes(_zip(GOOD))
    assert package.find_public_doc(zpath) == [
        "XBRL/PublicDoc/a.xbrl",
        "XBRL/PublicDoc/b.htm",
    ]
