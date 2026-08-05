"""``extract`` — offline Arelle loading and faithful XBRL projection.

Faithful XBRL *projection* (not full iXBRL reproduction): it maps a resolved XBRL
instance (loaded offline against a pinned taxonomy) onto the faithful-filing
schema. It captures the resolved layer — concept, value, context, unit,
dimensions, decimals/precision, nil, language, footnotes, and source location.
It does NOT synthesize iXBRL presentation provenance (lexical text, display,
transform/scale/sign, per-page location): those fields are OMITTED, and
``provenance_capabilities`` records that they were not extracted. The inline
document set adds them in a later commit.

:func:`extract_package` is the end-to-end orchestrator used by the CLI:
package ZIP → preferred ``.xbrl`` instance → offline Arelle load against a
pinned taxonomy → faithful-filing JSON + extraction-manifest.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from . import __version__
from . import package as package_mod
from . import schemas as schema_mod
from .exceptions import ConfigurationError, ExtractionError
from .hashing import CONTENT_HASH_ALGORITHM
from .models import (
    ExtractionConfiguration,
    ExtractionManifest,
    FaithfulFiling,
    SelectionRecord,
    SourcePackage,
    TaxonomyPackage,
)
from .package import (
    extract_safe,
    infer_document_id,
    select_preferred_xbrl,
    source_package_from_path,
)
from .taxonomy import OfflineArelleConfig, prepare_offline_taxonomy

FAITHFUL_FILING_SCHEMA_VERSION = "1.0.0"
MANIFEST_SCHEMA_VERSION = "1.0.0"
EXTRACTOR_NAME = "edinet-replay"
FILING_FILENAME = "faithful-filing.json"
MANIFEST_FILENAME = "extraction-manifest.json"

_XBRLI = "http://www.xbrl.org/2003/instance"

_TAXO_URL = re.compile(r"https?://[^\s'\"<>]+")
_MISSING_HINTS = ("offline", "unable to", "not loadable", "cannot", "no such", "failed to load")


class FaithfulExtractor(Protocol):
    """Produces a faithful filing from a stored package and pinned taxonomy."""

    def extract(
        self,
        package: SourcePackage,
        taxonomy: TaxonomyPackage,
        *,
        configuration: ExtractionConfiguration | None = None,
    ) -> FaithfulFiling: ...


def load_offline(entry_point: str, config: OfflineArelleConfig):
    """Load ``entry_point`` through Arelle with the network blocked, resolving the
    DTS only from the isolated taxonomy cache in ``config``. Arelle is imported
    lazily (requires the ``[xbrl]`` extra). Returns ``(cntlr, model, missing_urls)``.
    """
    from arelle import Cntlr

    cntlr = Cntlr.Cntlr(logFileName="logToBuffer")
    cntlr.webCache.cacheDir = config.web_cache_dir
    cntlr.webCache.workOffline = True
    model = cntlr.modelManager.load(str(entry_point))
    missing: set[str] = set()
    for rec in getattr(cntlr.logHandler, "logRecordBuffer", []):
        msg = rec.getMessage()
        if any(h in msg.lower() for h in _MISSING_HINTS):
            missing.update(_TAXO_URL.findall(msg))
    return cntlr, model, sorted(missing)


# --- projection helpers ------------------------------------------------------

def _raw_xml(el) -> str:
    from lxml import etree

    return etree.tostring(el, encoding="unicode")


def _c14n_sha256(el) -> str:
    # Canonical XML 2.0 without comments (lxml "c14n2", with_comments=False by
    # default). Declared as "xml-c14n2" in the output; lxml does not implement
    # C14N 1.1, so we declare exactly what we compute.
    from lxml import etree

    return hashlib.sha256(etree.tostring(el, method="c14n2")).hexdigest()


def _entity(ctx) -> dict:
    scheme, identifier = ctx.entityIdentifier
    return {"scheme": scheme, "identifier": identifier}


def _period(ctx) -> dict:
    period = ctx.find(f"{{{_XBRLI}}}period")
    if period is None:
        return {"type": "forever"}
    inst = period.find(f"{{{_XBRLI}}}instant")
    if inst is not None:
        return {"type": "instant", "instant": inst.text.strip()}
    start = period.find(f"{{{_XBRLI}}}startDate")
    end = period.find(f"{{{_XBRLI}}}endDate")
    if start is not None and end is not None:
        return {"type": "duration", "start": start.text.strip(), "end": end.text.strip()}
    return {"type": "forever"}


def _source(package_path: str, obj) -> dict:
    src = {"package_path": package_path}
    line = getattr(obj, "sourceline", None)
    if line:
        src["line"] = line
    element_id = obj.get("id")
    if element_id:
        src["element_id"] = element_id
    return src


def _dimensions(fact) -> dict:
    ctx = fact.context
    if ctx is None:
        raise ExtractionError(
            f"fact {fact.qname} has no context (tuple or malformed instance); "
            "context-less facts are not representable in faithful-filing 1.0.0"
        )
    dims = {"concept": str(fact.qname), "entity": _entity(ctx), "period": _period(ctx)}
    if fact.unit is not None:
        nums, dens = fact.unit.measures
        dims["unit"] = {
            "numerator": [str(m) for m in nums],
            "denominator": [str(m) for m in dens],
        }
    explicit, typed = {}, {}
    for dim_qname, dim_value in ctx.qnameDims.items():
        if dim_value.isExplicit:
            explicit[str(dim_qname)] = str(dim_value.memberQname)
        elif dim_value.isTyped:
            member = dim_value.typedMember
            typed[str(dim_qname)] = {
                "xml": _raw_xml(member),
                "canonical_xml_sha256": _c14n_sha256(member),
            }
    if explicit:
        dims["explicit_dimensions"] = explicit
    if typed:
        dims["typed_dimensions"] = typed
    return dims


def _project_context(ctx, package_path: str) -> dict:
    segment = ctx.find(f"{{{_XBRLI}}}entity/{{{_XBRLI}}}segment")
    scenario = ctx.find(f"{{{_XBRLI}}}scenario")
    return {
        "entity": _entity(ctx),
        "period": _period(ctx),
        "segment_xml": _raw_xml(segment) if segment is not None else None,
        "scenario_xml": _raw_xml(scenario) if scenario is not None else None,
        "source": _source(package_path, ctx),
    }


def _project_unit(unit, package_path: str) -> dict:
    nums, dens = unit.measures
    return {
        "numerator": [str(m) for m in nums],
        "denominator": [str(m) for m in dens],
        "source": _source(package_path, unit),
    }


def _source_fact_id(package_path, sourceline, concept_clark, ctx_ref, unit_ref, occurrence) -> str:
    key = "|".join(
        [
            package_path,
            str(sourceline) if sourceline else "",
            concept_clark,
            ctx_ref or "",
            unit_ref or "",
            str(occurrence),
        ]
    )
    return "fact-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def project_faithful_filing(
    model,
    *,
    document_id: str,
    package_path: str,
    schema_version: str = FAITHFUL_FILING_SCHEMA_VERSION,
) -> dict:
    """Project a resolved Arelle ``model`` onto the faithful-filing schema.

    ``package_path`` is the source instance path within the package (e.g.
    ``XBRL/PublicDoc/....xbrl``). iXBRL provenance layers are not populated here.
    """
    facts_out: dict = {}
    contexts_out: dict = {}
    units_out: dict = {}
    id_by_obj: dict = {}

    def sort_key(f):
        # Total order so the occurrence index (and thus every source_fact_id) is
        # deterministic regardless of Arelle's internal fact iteration order.
        # Two facts identical in all of these are true duplicates whose swap does
        # not change the output.
        ctx, unit = f.context, f.unit
        return (
            f.sourceline or -1,
            f.qname.clarkNotation,
            ctx.id if ctx is not None else "",
            unit.id if unit is not None else "",
            "" if f.isNil else (f.value or ""),
            f.decimals or "",
            f.precision or "",
            f.isNil,
        )

    occurrence: dict = {}
    for fact in sorted(model.facts, key=sort_key):
        ctx, unit = fact.context, fact.unit
        ctx_ref = ctx.id if ctx is not None else None
        unit_ref = unit.id if unit is not None else None
        clark = fact.qname.clarkNotation
        occ_key = (package_path, fact.sourceline, clark, ctx_ref, unit_ref)
        occ = occurrence.get(occ_key, 0)
        occurrence[occ_key] = occ + 1
        fid = _source_fact_id(package_path, fact.sourceline, clark, ctx_ref, unit_ref, occ)
        id_by_obj[fact] = fid

        entry = {
            "value": None if fact.isNil else fact.value,
            "nil": bool(fact.isNil),
            "dimensions": _dimensions(fact),
            "source_context_ref": ctx_ref,
            "source": _source(package_path, fact),
        }
        if unit_ref is not None:
            entry["source_unit_ref"] = unit_ref
        if fact.decimals is not None:
            entry["decimals"] = fact.decimals
        if fact.precision is not None:
            entry["precision"] = fact.precision
        if fact.xmlLang:
            entry["language"] = fact.xmlLang
        facts_out[fid] = entry

        if ctx_ref and ctx_ref not in contexts_out:
            contexts_out[ctx_ref] = _project_context(ctx, package_path)
        if unit_ref and unit_ref not in units_out:
            units_out[unit_ref] = _project_unit(unit, package_path)

    footnotes, relationships = _project_footnotes(model, id_by_obj)

    out = {
        "filing_schema_version": schema_version,
        "filing": {"document_id": document_id},
        "canonicalization": {
            "json_profile": "edinet-replay-canonical-json-v1",
            "xml_c14n": "xml-c14n2",
        },
        "provenance_capabilities": {
            "resolved_xbrl": True,
            "ixbrl_lexical": False,
            "ixbrl_presentation": False,
        },
        "facts": facts_out,
        "contexts": contexts_out,
        "units": units_out,
    }
    if footnotes:
        out["footnotes"] = footnotes
    if relationships:
        out["fact_footnote_relationships"] = relationships
    return out


def _project_footnotes(model, id_by_obj) -> tuple[dict, list]:
    from arelle import XbrlConst

    rels = model.relationshipSet(XbrlConst.factFootnote)
    footnotes: dict = {}
    out_rels: list = []
    if not rels:
        return footnotes, out_rels
    for rel in rels.modelRelationships:
        fact_id = id_by_obj.get(rel.fromModelObject)
        resource = rel.toModelObject
        if fact_id is None or resource is None:
            continue
        fn_id = resource.get("id")
        if not fn_id:
            # Deterministic id from content (Python's object hash is per-process
            # randomized and must never leak into the output).
            basis = "\x00".join(
                [
                    resource.stringValue or "",
                    getattr(resource, "role", None) or "",
                    getattr(resource, "xmlLang", None) or "",
                ]
            )
            fn_id = "fn-" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
        if fn_id not in footnotes:
            footnotes[fn_id] = {
                "role": getattr(resource, "role", None),
                "arcrole": rel.arcrole,
                "lang": getattr(resource, "xmlLang", None),
                "content": resource.stringValue,
            }
        out_rels.append({"fact_id": fact_id, "footnote_id": fn_id, "arcrole": rel.arcrole})
    out_rels.sort(key=lambda r: (r["fact_id"], r["footnote_id"], r["arcrole"] or ""))
    return footnotes, out_rels


def build_manifest(
    package: SourcePackage,
    taxonomy: TaxonomyPackage,
    selection: SelectionRecord,
    *,
    arelle_version: str,
    extractor_version: str,
    extraction_source: dict,
    generated_at: str,
    configuration: dict | None = None,
) -> ExtractionManifest:
    """Build an ``extraction-manifest`` document recording the full reproduction
    identity. Conforms to ``extraction-manifest-1.0.0.schema.json``. No secrets.
    """
    entries = []
    for e in package.entries:
        item = {"path": e.path, "sha256": e.sha256}
        if e.size_bytes is not None:
            item["size_bytes"] = e.size_bytes
        entries.append(item)

    if not package.retrieved_at:
        raise ConfigurationError(
            "source package retrieved_at is required for an extraction manifest"
        )
    source_package: dict = {
        "document_id": package.document_id,
        "raw_sha256": package.raw_sha256,
        "content_sha256": package.content_sha256,
        "content_hash_algorithm": CONTENT_HASH_ALGORITHM,
        "media_type": package.media_type,
        "retrieved_at": package.retrieved_at,
    }
    if package.size_bytes is not None:
        source_package["size_bytes"] = package.size_bytes
    if entries:
        source_package["entries"] = entries

    taxonomy_package: dict = {
        "identifier": taxonomy.identifier,
        "raw_sha256": taxonomy.raw_sha256,
        "content_sha256": taxonomy.content_sha256,
        "content_hash_algorithm": CONTENT_HASH_ALGORITHM,
        "resolution": "offline",
    }
    if taxonomy.version is not None:
        taxonomy_package["version"] = taxonomy.version

    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "source_package": source_package,
        "selection": {
            "selected_by": selection.selected_by,
            "selector_version": selection.selector_version,
            "parameters": dict(selection.parameters),
            "selected_document_id": selection.selected_document_id,
            "candidate_document_ids": list(selection.candidate_document_ids),
        },
        "taxonomy_package": taxonomy_package,
        "engine": {"name": "Arelle", "version": arelle_version},
        "extractor": {
            "name": EXTRACTOR_NAME,
            "version": extractor_version,
            "faithful_filing_schema_version": FAITHFUL_FILING_SCHEMA_VERSION,
        },
        "extraction": {"configuration": configuration or {}},
        "extraction_source": extraction_source,
        "generated_at": generated_at,
    }


@dataclass(frozen=True)
class ExtractArtifacts:
    """Outputs of one :func:`extract_package` run."""

    filing: FaithfulFiling
    manifest: ExtractionManifest
    source_package: SourcePackage
    taxonomy: TaxonomyPackage
    package_path_in_archive: str
    arelle_version: str
    filing_path: str | None = None
    manifest_path: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def extract_package(
    package_path: str | os.PathLike[str],
    *,
    taxonomy_identifier: str,
    document_id: str | None = None,
    selection: SelectionRecord | None = None,
    acquisition_record_path: str | os.PathLike[str] | None = None,
    taxonomy_zip: str | os.PathLike[str] | None = None,
    pins_dir: str | os.PathLike[str] | None = None,
    registry_dir: str | os.PathLike[str] | None = None,
    cache_root: str | os.PathLike[str] | None = None,
    output_dir: str | os.PathLike[str] | None = None,
    work_dir: str | os.PathLike[str] | None = None,
    generated_at: str | None = None,
    extractor_version: str | None = None,
    retrieved_at: str | None = None,
    validate: bool = True,
) -> ExtractArtifacts:
    """Extract a faithful filing + manifest from one submission ZIP.

    Requires the ``[xbrl]`` extra (Arelle + lxml). Taxonomy identity is never
    implicit: ``taxonomy_identifier`` must name a pin record, and the local
    taxonomy zip must match that pin's hashes.

    When ``output_dir`` is set, writes ``faithful-filing.json`` and
    ``extraction-manifest.json`` there after optional schema validation.
    """
    path = Path(package_path)
    if not path.is_file():
        raise ExtractionError(f"package not found: {path}")

    doc_id = document_id or infer_document_id(path)
    if not doc_id:
        raise ConfigurationError(
            "document_id is required (pass document_id= or use a store path "
            "packages/{document_id}/{raw_sha256}.zip)"
        )

    source = source_package_from_path(path, document_id=doc_id, retrieved_at=retrieved_at)
    record_path = (
        Path(acquisition_record_path)
        if acquisition_record_path is not None
        else package_mod.acquisition_record_path(path)
    )
    acquisition = (
        package_mod.load_acquisition_record(record_path, package=source)
        if record_path.is_file()
        else None
    )
    if acquisition is not None:
        source = source_package_from_path(
            path, document_id=doc_id, retrieved_at=acquisition.retrieved_at
        )
        if selection is None:
            selection = acquisition.selection
        elif selection != acquisition.selection:
            raise ConfigurationError(
                "selection conflicts with acquisition record; provenance records are immutable"
            )
    elif source.retrieved_at is None:
        raise ConfigurationError(
            "no acquisition record found; pass retrieved_at= with a verified retrieval timestamp "
            "or provide acquisition_record_path"
        )

    try:
        import arelle  # noqa: F401
        from arelle import Version
    except ImportError as exc:
        raise ConfigurationError(
            "Arelle is required for extract; install with "
            'pip install "edinet-replay[xbrl]"'
        ) from exc
    tax_ref, offline_cfg, _pin = prepare_offline_taxonomy(
        taxonomy_identifier,
        taxonomy_zip=taxonomy_zip,
        pins_dir=pins_dir,
        registry_dir=registry_dir,
        cache_root=cache_root,
    )

    own_work = work_dir is None
    if work_dir is not None:
        work = Path(work_dir)
    else:
        work = Path(tempfile.mkdtemp(prefix="edinet-replay-"))
    try:
        extracted_root = work / "package"
        if extracted_root.exists():
            shutil.rmtree(extracted_root)
        extract_safe(path, extracted_root)
        rel_path, extraction_source = select_preferred_xbrl(extracted_root)
        entry = extracted_root / rel_path
        if not entry.is_file():
            raise ExtractionError(f"selected entry missing after extract: {rel_path}")

        _cntlr, model, missing = load_offline(str(entry), offline_cfg)
        if model is None:
            raise ExtractionError(
                f"Arelle failed to load {rel_path}"
                + (f"; missing DTS urls: {missing}" if missing else "")
            )
        if missing:
            raise ExtractionError(
                f"offline DTS resolution incomplete for {rel_path}; "
                f"missing: {missing}"
            )

        filing = project_faithful_filing(
            model, document_id=doc_id, package_path=rel_path
        )
        when = generated_at or _utc_now()
        sel = selection or SelectionRecord(
            selected_by="explicit_document",
            selector_version="0",
            selected_document_id=doc_id,
            candidate_document_ids=[doc_id],
            parameters={},
        )
        if sel.selected_document_id != doc_id:
            raise ConfigurationError(
                f"selection.selected_document_id {sel.selected_document_id!r} "
                f"!= document_id {doc_id!r}"
            )
        arelle_version = Version.__version__
        ext_ver = extractor_version or __version__
        manifest = build_manifest(
            source,
            tax_ref,
            sel,
            arelle_version=arelle_version,
            extractor_version=ext_ver,
            extraction_source=extraction_source,
            generated_at=when,
        )

        if validate:
            schema_mod.validate(filing, schema_mod.FAITHFUL_FILING_SCHEMA)
            schema_mod.validate(manifest, schema_mod.MANIFEST_SCHEMA)

        filing_path = manifest_path = None
        if output_dir is not None:
            out = Path(output_dir)
            filing_path = str(out / FILING_FILENAME)
            manifest_path = str(out / MANIFEST_FILENAME)
            _write_json(Path(filing_path), dict(filing))
            _write_json(Path(manifest_path), dict(manifest))

        return ExtractArtifacts(
            filing=filing,
            manifest=manifest,
            source_package=source,
            taxonomy=tax_ref,
            package_path_in_archive=rel_path,
            arelle_version=arelle_version,
            filing_path=filing_path,
            manifest_path=manifest_path,
        )
    finally:
        if own_work and work.exists():
            shutil.rmtree(work, ignore_errors=True)
