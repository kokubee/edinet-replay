"""Tests for package storage and safe extraction."""
import io
import zipfile

import pytest

from edinet_replay import package
from edinet_replay.exceptions import (
    PackageConflictError,
    PackageValidationError,
    UnsafeArchiveError,
)
from edinet_replay.hashing import zip_content_sha256_v1

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


def test_infer_document_id_from_store_layout(tmp_path):
    store = tmp_path / "packages" / "S100W1NC" / ("a" * 64 + ".zip")
    store.parent.mkdir(parents=True)
    store.write_bytes(b"x")
    assert package.infer_document_id(store) == "S100W1NC"
    assert package.infer_document_id(tmp_path / "other.zip") is None


def test_select_preferred_xbrl_from_manifest(tmp_path):
    public = tmp_path / "XBRL" / "PublicDoc"
    public.mkdir(parents=True)
    (public / "chosen.xbrl").write_text("<xbrl/>", encoding="utf-8")
    (public / "other.xbrl").write_text("<xbrl/>", encoding="utf-8")
    (public / "manifest_PublicDoc.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns="http://disclosure.edinet-fsa.go.jp/2013/manifest">
  <list>
    <instance preferredFilename="chosen.xbrl"/>
  </list>
</manifest>
""",
        encoding="utf-8",
    )
    rel, meta = package.select_preferred_xbrl(tmp_path)
    assert rel == "XBRL/PublicDoc/chosen.xbrl"
    assert meta == {
        "kind": "xbrl-instance",
        "package_path": rel,
        "selected_from_manifest": True,
        "preferred_filename": True,
    }


def test_select_preferred_xbrl_single_file_fallback(tmp_path):
    public = tmp_path / "XBRL" / "PublicDoc"
    public.mkdir(parents=True)
    (public / "only.xbrl").write_text("<xbrl/>", encoding="utf-8")
    rel, meta = package.select_preferred_xbrl(tmp_path)
    assert rel == "XBRL/PublicDoc/only.xbrl"
    assert meta["selected_from_manifest"] is False


def test_select_preferred_xbrl_rejects_ambiguous(tmp_path):
    public = tmp_path / "XBRL" / "PublicDoc"
    public.mkdir(parents=True)
    (public / "a.xbrl").write_text("<xbrl/>", encoding="utf-8")
    (public / "b.xbrl").write_text("<xbrl/>", encoding="utf-8")
    with pytest.raises(PackageValidationError, match="multiple"):
        package.select_preferred_xbrl(tmp_path)


# --- bounded archive access --------------------------------------------------

BOMB = [("bomb.bin", b"\x00" * (8 * 1024 * 1024))]


def test_inventory_rejects_high_compression_zip_bomb():
    data = _zip(BOMB)
    assert len(data) < 1024 * 1024  # compressed is tiny; declared size is 8 MiB
    with pytest.raises(UnsafeArchiveError, match="compression ratio"):
        package.inventory(data)


def test_zip_content_hash_rejects_high_compression_zip_bomb(tmp_path):
    zpath = tmp_path / "bomb.zip"
    zpath.write_bytes(_zip(BOMB))
    with pytest.raises(UnsafeArchiveError, match="compression ratio"):
        zip_content_sha256_v1(zpath)


def test_cli_inspect_rejects_zip_bomb_without_reading_it(tmp_path, capsys):
    from edinet_replay import cli

    zpath = tmp_path / "bomb.zip"
    zpath.write_bytes(_zip(BOMB))
    assert cli.main(["inspect", str(zpath)]) == 1
    err = capsys.readouterr().err
    assert "compression ratio" in err


def test_extract_safe_rejects_zip_bomb_before_writing(tmp_path):
    zpath = tmp_path / "bomb.zip"
    zpath.write_bytes(_zip(BOMB))
    out = tmp_path / "out"
    with pytest.raises(UnsafeArchiveError, match="compression ratio"):
        package.extract_safe(zpath, out)
    if out.exists():
        assert list(out.rglob("*")) == []


# --- manifest preferredFilename ---------------------------------------------


@pytest.mark.parametrize(
    "preferred",
    ["../evil.xbrl", "/etc/evil.xbrl", "sub\\evil.xbrl", "sub/evil.xbrl", "C:evil.xbrl"],
)
def test_preferred_filename_traversal_rejected(tmp_path, preferred):
    public = tmp_path / "XBRL" / "PublicDoc"
    public.mkdir(parents=True)
    (public / "chosen.xbrl").write_text("<xbrl/>", encoding="utf-8")
    (public / "manifest_PublicDoc.xml").write_text(
        f"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns="http://disclosure.edinet-fsa.go.jp/2013/manifest">
  <list>
    <instance preferredFilename="{preferred}"/>
  </list>
</manifest>
""",
        encoding="utf-8",
    )
    with pytest.raises(PackageValidationError, match="preferredFilename"):
        package.select_preferred_xbrl(tmp_path)


def test_manifest_with_doctype_is_rejected(tmp_path):
    public = tmp_path / "XBRL" / "PublicDoc"
    public.mkdir(parents=True)
    (public / "manifest_PublicDoc.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE manifest [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<manifest xmlns="http://disclosure.edinet-fsa.go.jp/2013/manifest">
  <list><instance preferredFilename="chosen.xbrl"/></list>
</manifest>
""",
        encoding="utf-8",
    )
    with pytest.raises(PackageValidationError, match="DOCTYPE"):
        package.select_preferred_xbrl(tmp_path)


def test_cli_inspect_reports_hashes_for_a_normal_package(tmp_path, capsys):
    from edinet_replay import cli

    zpath = tmp_path / "ok.zip"
    zpath.write_bytes(_zip(GOOD))
    assert cli.main(["inspect", str(zpath)]) == 0
    out = capsys.readouterr().out
    assert "content_sha256:" in out
    assert "XBRL/PublicDoc/a.xbrl" in out
