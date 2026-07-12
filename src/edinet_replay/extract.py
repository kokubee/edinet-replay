"""``extract`` — offline Arelle loading and faithful XBRL projection.

Faithful XBRL *projection* (not full iXBRL reproduction): it maps a resolved XBRL
instance (loaded offline against a pinned taxonomy) onto the faithful-filing
schema. It captures the resolved layer — concept, value, context, unit,
dimensions, decimals/precision, nil, language, footnotes, and source location.
It does NOT synthesize iXBRL presentation provenance (lexical text, display,
transform/scale/sign, per-page location): those fields are OMITTED, and
``provenance_capabilities`` records that they were not extracted. The inline
document set adds them in a later commit.
"""
from __future__ import annotations

import hashlib
import re
from typing import Protocol

from .hashing import CONTENT_HASH_ALGORITHM
from .models import (
    ExtractionConfiguration,
    ExtractionManifest,
    FaithfulFiling,
    SelectionRecord,
    SourcePackage,
    TaxonomyPackage,
)
from .taxonomy import OfflineArelleConfig

FAITHFUL_FILING_SCHEMA_VERSION = "1.0.0"
MANIFEST_SCHEMA_VERSION = "1.0.0"
EXTRACTOR_NAME = "edinet-replay"

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
        ctx, unit = f.context, f.unit
        return (
            f.sourceline or -1,
            f.qname.clarkNotation,
            ctx.id if ctx is not None else "",
            unit.id if unit is not None else "",
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
            "json_profile": "faithful-filing-jcs-v1",
            "xml_c14n": "xml-c14n-1.1-without-comments",
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
        fn_id = resource.get("id") or f"fn-{abs(hash(resource)) % (1 << 32):08x}"
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

    source_package: dict = {
        "document_id": package.document_id,
        "raw_sha256": package.raw_sha256,
        "content_sha256": package.content_sha256,
        "content_hash_algorithm": CONTENT_HASH_ALGORITHM,
        "media_type": package.media_type,
        "retrieved_at": package.retrieved_at or generated_at,
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
