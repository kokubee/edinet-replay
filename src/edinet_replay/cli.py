"""``edinet-replay`` command-line interface (pre-alpha).

Implemented today: ``validate`` (manifest/filing against their schemas) and
``inspect`` (a package ZIP's raw/content hashes and inventory). ``fetch`` and
``extract`` are declared but not yet implemented and exit with a clear message.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from collections.abc import Sequence
from pathlib import Path

from . import __version__, schemas
from .exceptions import EdinetReplayError
from .hashing import content_sha256_v1, sha256_bytes

_VALIDATE_SCHEMAS = {
    "manifest": schemas.MANIFEST_SCHEMA,
    "filing": schemas.FAITHFUL_FILING_SCHEMA,
}
_NOT_IMPLEMENTED = "Command not implemented in this pre-alpha release."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="edinet-replay",
        description="Reproducible, provenance-preserving EDINET extraction (pre-alpha).",
    )
    parser.add_argument("--version", action="version", version=f"edinet-replay {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    validate = sub.add_parser(
        "validate", help="Validate a manifest or faithful filing against its schema."
    )
    validate.add_argument("kind", choices=sorted(_VALIDATE_SCHEMAS))
    validate.add_argument("file", help="Path to the JSON document to validate.")

    inspect = sub.add_parser(
        "inspect", help="Show a package ZIP's raw/content hashes and inventory."
    )
    inspect.add_argument("package", help="Path to a submission ZIP.")

    fetch = sub.add_parser("fetch", help="Retrieve a filing package from EDINET (planned).")
    fetch.add_argument("--date", help="Submission date, YYYY-MM-DD.")
    fetch.add_argument("--edinet-code", help="Issuer EDINET code, e.g. E02144.")

    extract = sub.add_parser(
        "extract", help="Produce faithful JSON from a package via Arelle (planned)."
    )
    extract.add_argument("package", nargs="?", help="Path to a stored package.")

    return parser


def _cmd_validate(args: argparse.Namespace) -> int:
    instance = json.loads(Path(args.file).read_text(encoding="utf-8"))
    schema_name = _VALIDATE_SCHEMAS[args.kind]
    schemas.validate(instance, schema_name)
    print(f"OK: {args.file} conforms to {schema_name}")
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    path = Path(args.package)
    raw = path.read_bytes()
    with zipfile.ZipFile(path) as zf:
        entries = [
            (info.filename, info.file_size) for info in zf.infolist() if not info.is_dir()
        ]
        files = [(name, zf.read(name)) for name, _ in entries]
    print(f"package:        {path}")
    print(f"raw_sha256:     {sha256_bytes(raw)}")
    print(f"content_sha256: {content_sha256_v1(files)}")
    print(f"entries:        {len(entries)}")
    for name, size in entries:
        print(f"  {size:>10}  {name}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    try:
        if args.command == "validate":
            return _cmd_validate(args)
        if args.command == "inspect":
            return _cmd_inspect(args)
    except EdinetReplayError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (OSError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    raise SystemExit(f"{args.command}: {_NOT_IMPLEMENTED}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
