"""``edinet-replay`` command-line interface (pre-alpha skeleton).

Subcommands are declared so the shape is visible, but their bodies are not yet
implemented. ``edinet-replay --help`` works today.
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="edinet-replay",
        description="Reproducible, provenance-preserving extraction for EDINET filings (pre-alpha).",
    )
    parser.add_argument("--version", action="version", version=f"edinet-replay {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    fetch = sub.add_parser("fetch", help="Retrieve a filing package from EDINET (planned).")
    fetch.add_argument("--date", help="Submission date, YYYY-MM-DD.")
    fetch.add_argument("--edinet-code", help="Issuer EDINET code, e.g. E02144.")

    inspect = sub.add_parser("inspect", help="Show a stored package's inventory and hashes (planned).")
    inspect.add_argument("package", nargs="?", help="Path to a stored package.")

    extract = sub.add_parser("extract", help="Produce faithful JSON from a package via Arelle (planned).")
    extract.add_argument("package", nargs="?", help="Path to a stored package.")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    raise SystemExit(f"'{args.command}' is not implemented yet (pre-alpha).")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
