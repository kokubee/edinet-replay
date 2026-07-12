"""JSON Schema validation of the minimal fixtures.

Uses jsonschema only. Confirms the fixtures conform to the versioned contracts.
"""
import json
import pathlib

from jsonschema import Draft202012Validator

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
FIX = ROOT / "tests" / "fixtures" / "minimal"


def _validate(instance_name: str, schema_name: str) -> None:
    schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
    instance = json.loads((FIX / instance_name).read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(instance)


def test_manifest_conforms_to_schema() -> None:
    _validate("extraction-manifest.json", "extraction-manifest-1.0.0.schema.json")


def test_faithful_filing_conforms_to_schema() -> None:
    _validate("faithful-filing.json", "faithful-filing-1.0.0.schema.json")


def test_schemas_are_valid_draft202012() -> None:
    for name in (
        "extraction-manifest-1.0.0.schema.json",
        "faithful-filing-1.0.0.schema.json",
    ):
        Draft202012Validator.check_schema(
            json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
        )
