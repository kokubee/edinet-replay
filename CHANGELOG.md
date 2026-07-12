# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and versions follow
[PEP 440](https://peps.python.org/pep-0440/) / semantic versioning.

## [0.1.0-alpha.1] — Unreleased

First pre-alpha. The output contracts and reproducibility model are defined; the
resolved-XBRL projection works end to end offline. The retrieval client and the
inline (iXBRL) presentation layer are not yet implemented.

### Added

- Versioned JSON Schemas: `extraction-manifest-1.0.0` and `faithful-filing-1.0.0`.
- Content hashing (`entry-path-and-content-sha256-v1`) and the canonical JSON
  profile (`edinet-replay-canonical-json-v1`). The typed-dimension XML
  canonicalization profile is XML Canonicalization 2.0, as implemented by lxml's
  `c14n2` method (declared as `xml-c14n2`).
- Package storage with dual hashes, Zip-Slip-safe extraction, and idempotency.
- Taxonomy registry with pinned, hash-verified, **offline** DTS resolution using
  an isolated, content-hash-namespaced Arelle web cache (never touches Arelle's
  global cache).
- Mechanical `catalog.filter_documents` and explicit
  `selectors.latest_original_filing`.
- Faithful XBRL projection (resolved layer only): concept, value, entity, period,
  explicit/typed dimensions, unit, decimals/precision, nil, language, footnotes,
  and source location. iXBRL presentation provenance is deferred.
- CLI: `validate` (manifest/filing) and `inspect` (package hashes/inventory);
  `fetch`/`extract` are declared but not yet implemented.
- Golden regressions for E04236 (JP GAAP) and E00492 (IFRS), byte-stable across
  independent runs.

### Known limitations

- No retrieval client yet (`fetch`) and no inline-XBRL document-set extraction
  (no lexical/display/transform provenance).
- Real-data golden tests require local EDINET filings and taxonomy packages.
