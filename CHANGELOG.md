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
- Live EDINET API v2 client: `EdinetClient.list_documents()` /
  `EdinetClient.download_document()`. Authenticates via the
  `Ocp-Apim-Subscription-Key` header (the key never appears in URLs, logs, or
  exception messages), translates EDINET's body-level statuses — observed
  API-level errors may arrive as HTTP 200 with the effective status in the
  body — into a typed hierarchy
  (`EdinetAuthenticationError` for body `StatusCode` 401,
  `DocumentNotFoundError` for body 404, `EdinetResponseError` for unexpected
  payloads), validates content types, distinguishes ZIP payloads from JSON
  error bodies, retries only real HTTP 429/5xx, and returns result types
  carrying `retrieved_at` and `api_version`. New models:
  `DocumentListResult`, `DocumentDownload`; `DocumentMetadata` gains
  `parent_document_id` (and `is_amendment` is derived from it). The client's
  HTTP layer is injectable, so unit tests run without any key; optional live
  tests are gated behind `EDINET_REPLAY_LIVE_API_TESTS=1`.

- CLI `fetch`: wires the client, `catalog.filter_documents`,
  `selectors.latest_original_filing`, and `package.store` together with no new
  policy logic. Three modes: `--document-id` (explicit fetch into the
  content-addressed store), `--date ... --list-only` (filtered document list
  as JSON), and `--date ... --select latest-original-filing` (explicit,
  versioned selection; the printed record keeps the full candidate set).
  Selection is never implicit, and the API key is read only from
  `EDINET_API_KEY` — there is deliberately no `--api-key` flag.

### Changed

- `EdinetClient` constructor: the undocumented `session` stub parameter is now
  `transport` (an injectable minimal HTTP layer); `retry_backoff` added.

### Known limitations

- No CLI `extract` yet, and no inline-XBRL document-set extraction (no
  lexical/display/transform provenance).
- Real-data golden tests require local EDINET filings and taxonomy packages.
