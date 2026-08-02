"""``edinet-replay`` command-line interface (pre-alpha).

Implemented today: ``validate`` (manifest/filing against their schemas),
``inspect`` (a package ZIP's raw/content hashes and inventory), ``fetch``
(document listing and package retrieval), and ``extract`` (offline Arelle
projection of a stored package to faithful-filing + extraction-manifest).

``fetch`` wires the existing modules together without adding policy logic:

- ``fetch --document-id DOCID --store DIR`` downloads one named document and
  stores it content-addressed (an *explicit* selection).
- ``fetch --date YYYY-MM-DD [--edinet-code E] [--doc-type T] --list-only``
  prints the (mechanically filtered) document list as JSON, no download.
- ``fetch --date D --edinet-code E --select latest-original-filing --store DIR``
  lists, filters, applies the named selector, downloads, and stores. Selection
  is never implicit: ``--date`` mode requires ``--list-only`` or ``--select``.

``extract`` requires an explicit ``--taxonomy`` pin identifier and writes
``faithful-filing.json`` + ``extraction-manifest.json`` under ``--output-dir``.

The API key is read only from ``EDINET_API_KEY``; there is deliberately no
``--api-key`` flag (a key on the command line leaks into shell history and the
process list). All results are machine-readable JSON on stdout.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import zipfile
from collections.abc import Sequence
from pathlib import Path

from . import __version__, catalog, extract, package, schemas, selectors
from .client import EdinetClient
from .exceptions import EdinetReplayError
from .hashing import content_sha256_v1, sha256_bytes
from .models import DocumentListResult, SelectionRecord

_VALIDATE_SCHEMAS = {
    "manifest": schemas.MANIFEST_SCHEMA,
    "filing": schemas.FAITHFUL_FILING_SCHEMA,
}


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

    fetch = sub.add_parser(
        "fetch",
        help="List EDINET documents and retrieve filing packages.",
        description=(
            "Retrieve from the EDINET API. The key is read from EDINET_API_KEY "
            "(never passed on the command line). Selection is never implicit: "
            "with --date, pass --list-only to just list, or --select to apply a "
            "named, versioned selection strategy."
        ),
    )
    fetch.add_argument("--document-id", help="Fetch this exact docID (explicit selection).")
    fetch.add_argument("--date", help="Submission date, YYYY-MM-DD.")
    fetch.add_argument("--edinet-code", help="Issuer EDINET code, e.g. E02144.")
    fetch.add_argument(
        "--doc-type",
        help=(
            "EDINET docTypeCode (e.g. 120) or a named alias: "
            + ", ".join(sorted(catalog.DOCUMENT_TYPES))
        ),
    )
    fetch.add_argument(
        "--list-only",
        action="store_true",
        help="Print the (filtered) document list as JSON without downloading.",
    )
    fetch.add_argument(
        "--select",
        choices=["latest-original-filing"],
        help="Named selection strategy to choose one document from the filtered list.",
    )
    fetch.add_argument("--store", help="Package store directory (required when downloading).")

    extract_p = sub.add_parser(
        "extract",
        help="Produce faithful JSON + manifest from a package via offline Arelle.",
        description=(
            "Extract a faithful-filing document and an extraction-manifest from "
            "one submission ZIP. Taxonomy identity is never implicit: pass "
            "--taxonomy with a pin identifier (e.g. edinet-fsa-2024-11-01). "
            "Requires the [xbrl] extra. Writes faithful-filing.json and "
            "extraction-manifest.json under --output-dir."
        ),
    )
    extract_p.add_argument("package", help="Path to a submission ZIP.")
    extract_p.add_argument(
        "--taxonomy",
        required=True,
        help="Pinned taxonomy identifier (e.g. edinet-fsa-2024-11-01).",
    )
    extract_p.add_argument(
        "--output-dir",
        "-o",
        required=True,
        help="Directory for faithful-filing.json and extraction-manifest.json.",
    )
    extract_p.add_argument(
        "--document-id",
        help=(
            "EDINET docID. Optional when the package path follows the store "
            "layout packages/{document_id}/{raw_sha256}.zip."
        ),
    )
    extract_p.add_argument(
        "--taxonomy-zip",
        help="Path to the taxonomy distribution ZIP (default: ~/.cache/edinet-replay/...).",
    )
    extract_p.add_argument(
        "--pins-dir",
        help="Directory of taxonomy pin JSON records (default: search path).",
    )
    extract_p.add_argument(
        "--registry-dir",
        help="Taxonomy registry directory (default: ~/.cache/edinet-replay/registry).",
    )
    extract_p.add_argument(
        "--cache-root",
        help="Isolated Arelle web-cache root (default: ~/.cache/edinet-replay/arelle-web-cache).",
    )

    return parser


def _resolve_doc_type(value: str | None) -> str | None:
    if value is None:
        return None
    return catalog.DOCUMENT_TYPES.get(value, value)


def _document_as_dict(doc) -> dict:
    return dataclasses.asdict(doc)


def _download_and_store(
    client: EdinetClient, document_id: str, store_dir: str, selection: SelectionRecord
) -> dict:
    download = client.download_document(document_id)
    stored = package.store(
        download.content,
        document_id=document_id,
        dest_dir=store_dir,
        retrieved_at=download.retrieved_at,
    )
    return {
        "document_id": document_id,
        "package": {
            "path": stored.path,
            "raw_sha256": stored.raw_sha256,
            "content_sha256": stored.content_sha256,
            "media_type": stored.media_type,
            "size_bytes": stored.size_bytes,
        },
        "retrieval": {
            "retrieved_at": download.retrieved_at,
            "api_version": download.api_version,
        },
        "selection": dataclasses.asdict(selection),
    }


def _list_payload(listing: DocumentListResult, documents, filter_params: dict) -> dict:
    return {
        "date": listing.date,
        "retrieved_at": listing.retrieved_at,
        "api_version": listing.api_version,
        "result_count": listing.result_count,
        "process_datetime": listing.process_datetime,
        "filter": filter_params,
        "documents": [_document_as_dict(doc) for doc in documents],
    }


def _cmd_fetch(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.document_id and (args.date or args.list_only or args.select):
        parser.error("--document-id cannot be combined with --date/--list-only/--select")
    if not args.document_id and not args.date:
        parser.error("pass --document-id, or --date with --list-only or --select")

    client = EdinetClient()

    if args.document_id:
        if not args.store:
            parser.error("--store is required when downloading")
        selection = SelectionRecord(
            selected_by="explicit_document",
            selector_version="0",
            selected_document_id=args.document_id,
            candidate_document_ids=[args.document_id],
            parameters={},
        )
        record = _download_and_store(client, args.document_id, args.store, selection)
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0

    # --date modes: selection must be explicit.
    if not args.list_only and not args.select:
        parser.error("--date requires --list-only or an explicit --select strategy")

    doc_type = _resolve_doc_type(args.doc_type)
    listing = client.list_documents(args.date)
    filter_params = {
        "date": args.date,
        "edinet_code": args.edinet_code,
        "doc_type_codes": [doc_type] if doc_type else None,
    }
    filtered = catalog.filter_documents(
        listing.documents,
        edinet_code=args.edinet_code,
        doc_type_codes=[doc_type] if doc_type else None,
    )

    if args.list_only:
        payload = _list_payload(listing, filtered, filter_params)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if not args.edinet_code:
        parser.error("--select requires --edinet-code")
    if not args.store:
        parser.error("--store is required when downloading")
    selection = selectors.latest_original_filing(filtered, parameters=filter_params)
    record = _download_and_store(
        client, selection.selected_document_id, args.store, selection
    )
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


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


def _cmd_extract(args: argparse.Namespace) -> int:
    result = extract.extract_package(
        args.package,
        taxonomy_identifier=args.taxonomy,
        document_id=args.document_id,
        taxonomy_zip=args.taxonomy_zip,
        pins_dir=args.pins_dir,
        registry_dir=args.registry_dir,
        cache_root=args.cache_root,
        output_dir=args.output_dir,
    )
    payload = {
        "document_id": result.source_package.document_id,
        "package": {
            "path": result.source_package.path,
            "raw_sha256": result.source_package.raw_sha256,
            "content_sha256": result.source_package.content_sha256,
        },
        "extraction_source": dict(result.manifest["extraction_source"]),
        "taxonomy": {
            "identifier": result.taxonomy.identifier,
            "version": result.taxonomy.version,
            "content_sha256": result.taxonomy.content_sha256,
        },
        "engine": {"name": "Arelle", "version": result.arelle_version},
        "extractor": {"name": extract.EXTRACTOR_NAME, "version": __version__},
        "filing": {
            "path": result.filing_path,
            "fact_count": len(result.filing.get("facts", {})),
            "context_count": len(result.filing.get("contexts", {})),
            "unit_count": len(result.filing.get("units", {})),
        },
        "manifest": {"path": result.manifest_path},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
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
        if args.command == "fetch":
            return _cmd_fetch(args, parser)
        if args.command == "extract":
            return _cmd_extract(args)
    except EdinetReplayError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
