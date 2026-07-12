"""Loading and validation against the versioned JSON Schemas.

Schemas are resolved either from the packaged copy (in a built wheel) or, when
running from a source checkout, from the repository's top-level ``schemas/``
directory. Validation is mandatory wherever a manifest or faithful filing is
produced or consumed.
"""
from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .exceptions import SchemaValidationError

MANIFEST_SCHEMA = "extraction-manifest-1.0.0.schema.json"
FAITHFUL_FILING_SCHEMA = "faithful-filing-1.0.0.schema.json"


def _schema_dir() -> Path:
    here = Path(__file__).resolve()
    packaged = here.parent / "schemas"
    if packaged.is_dir():
        return packaged
    return here.parents[2] / "schemas"


@cache
def load_schema(name: str) -> dict[str, Any]:
    return json.loads((_schema_dir() / name).read_text(encoding="utf-8"))


def validate(instance: Any, schema_name: str) -> None:
    """Validate ``instance`` against ``schema_name``; raise on the first error."""
    validator = Draft202012Validator(load_schema(schema_name))
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        location = list(first.path)
        raise SchemaValidationError(f"{schema_name}: {first.message} (at {location})")
