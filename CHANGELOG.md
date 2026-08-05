# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and versions follow
[PEP 440](https://peps.python.org/pep-0440/) / semantic versioning.

## [Unreleased]

### Added

- Immutable acquisition records beside content-addressed ZIPs. `fetch` now
  persists the actual EDINET retrieval time, API version, package hashes, and
  explicit selection record; `extract` verifies and carries that provenance
  into the manifest instead of substituting extraction time for retrieval time.

## [0.1.0-beta.1] — 2026-08-02

First **beta**. The β completion bar is met for resolved XBRL: an explicit
EDINET ``document_id`` can be fetched as an official ZIP, extracted offline
against a hash-pinned FSA taxonomy via Arelle, and schema-validated as
faithful-filing + extraction-manifest JSON. A minimal multi-standard corpus
pins expected canonical hashes for one JP GAAP, one IFRS, and one US GAAP
annual report. Inline XBRL presentation provenance remains deferred.

### Added

- CLI ``extract`` and the ``extract.extract_package`` orchestrator: given an
  explicit submission ZIP and a pinned taxonomy identifier, select the preferred
  ``.xbrl`` instance (from ``manifest_PublicDoc.xml`` preferredFilename, else
  the sole PublicDoc ``.xbrl``), load it offline through Arelle against a
  hash-verified taxonomy, write ``faithful-filing.json`` +
  ``extraction-manifest.json``, and schema-validate both. Taxonomy identity is
  never implicit (``--taxonomy`` required). Completes the
  ``fetch → extract → validate`` vertical path for resolved XBRL.
- **β corpus v1** (`corpus/beta-v1/`): one JP GAAP (E04236/S100W1NC), one IFRS
  (E00492/S100VH9B), one US GAAP (E01532/S100VXAI) entry with fixed docIDs,
  dual package hashes, taxonomy pins, and committed canonical outputs under
  `tests/golden/`. Catalog integrity tests run without local filings.
- README leads with a 30-second demo (GIF + commands + fact traced to ZIP line
  4943). Regenerator: `tools/render_demo_gif.py`.

### Fixed

- Package ``__version__`` now matches the declared release (was still
  ``0.1.0a1`` after the alpha.2 cut; now ``0.1.0b1``).

### Changed

- Project status: pre-alpha → **beta** (PyPI classifier, README, package
  metadata). Still best-effort; not production-certified.

## [0.1.0-alpha.2] — 2026-07-21

Pre-alpha. `0.1.0-alpha.1` was tagged on 2026-07-12, before the EDINET API v2
client and the CLI `fetch` wiring landed on `main`; both are included here.
Otherwise the scope is unchanged.

First pre-alpha. The output contracts and reproducibility model are defined; the
resolved-XBRL projection works end to end offline, and `fetch` now retrieves,
selects, and stores real filings through the live EDINET API. The inline (iXBRL)
presentation layer is not yet implemented.

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
- CLI: `validate` (manifest/filing) and `inspect` (package hashes/inventory).
  `fetch` is implemented (see below); `extract` landed after this tag (see
  Unreleased).
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

- No inline-XBRL document-set extraction (no lexical/display/transform
  provenance). CLI `extract` projects the resolved XBRL instance only.
- Real-data golden tests require local EDINET filings and taxonomy packages.
