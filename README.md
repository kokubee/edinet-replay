# EDINET Replay

Toward reproducible, verifiable access to Japan's EDINET corporate disclosures.

EDINET Replay is an open-source project for developing a reproducible, provenance-preserving extraction workflow for Japan's EDINET corporate filings.

It defines versioned schemas and reproducibility contracts for preserving official filing packages, resolving XBRL and Inline XBRL through [Arelle](https://arelle.org/), and producing machine-readable representations that remain traceable to their source filings.

The project is designed for **data engineers, quantitative researchers, XBRL implementers, ESG data users, academic researchers, financial data providers, and the data teams of institutional investors** who need verifiable access to Japanese corporate disclosures. General retail investors are unlikely to use it directly.

> **Project status: pre-alpha.** The vertical path `fetch → extract → validate` works for resolved XBRL instances against pinned FSA taxonomies. A minimal multi-standard **β corpus** (JP GAAP / IFRS / US GAAP) is published under [`corpus/`](corpus/). Inline XBRL presentation provenance and PyPI packaging are still incomplete.

## What is EDINET?

EDINET is Japan's statutory electronic disclosure system, operated by the Financial Services Agency (FSA). It is broadly comparable to the U.S. SEC's EDGAR system.

## Why this project exists

EDINET filings are publicly available, but reproducible use remains difficult because:

- filing packages contain complex XBRL and Inline XBRL structures;
- taxonomy versions change over time;
- extracted values may lose context, units, dimensions, or source provenance;
- normalized financial databases often do not disclose how original facts were transformed.

EDINET Replay focuses on **faithful reproduction rather than financial interpretation.** It aims to preserve the source facts first. Mapping, normalization, comparability assessment, and investment analysis belong in separate downstream layers.

## What is available today

- Versioned JSON Schemas for extraction manifests and faithful filing representations
- Specifications for package content hashing and canonical JSON serialization
- Validation fixtures covering numeric, textual, dimensional, nil, unit, and footnote structures
- Schema and semantic validation tests
- Documentation of the intended provenance and reproducibility model
- An EDINET API v2 client for the daily document list and raw package download
- CLI `fetch` / `extract` / `validate` / `inspect` — retrieve a package, project a faithful filing offline through Arelle against a pinned taxonomy, and validate both outputs
- β corpus v1 — fixed docIDs and expected canonical hashes for one JP GAAP, one IFRS, and one US GAAP annual report ([`corpus/`](corpus/))

### Vertical path (resolved XBRL)

Requires `pip install -e ".[dev,xbrl]"`, an `EDINET_API_KEY`, and a pin-matching FSA taxonomy zip under `~/.cache/edinet-replay/taxonomies/<id>/1c_Taxonomy.zip` (see `taxonomies/*.json`).

```console
$ export EDINET_API_KEY=...   # never pass the key on the command line
$ edinet-replay fetch --document-id S100W1NC --store ./store
$ edinet-replay extract ./store/packages/S100W1NC/<raw_sha256>.zip \
    --taxonomy edinet-fsa-2024-11-01 -o ./out
$ edinet-replay validate filing ./out/faithful-filing.json
$ edinet-replay validate manifest ./out/extraction-manifest.json
```

`extract` selects the preferred `.xbrl` instance from `manifest_PublicDoc.xml` (or the sole PublicDoc `.xbrl`), loads it offline, and writes `faithful-filing.json` plus `extraction-manifest.json`. Facts keep package-relative paths and line numbers back into the source ZIP. Taxonomy identity is never implicit: `--taxonomy` is required and the local zip is hash-checked against the pin.

### Retrieval example

```python
from edinet_replay.client import EdinetClient

client = EdinetClient()  # key from EDINET_API_KEY (sent as a header, never in URLs)

listing = client.list_documents("2025-06-27")
originals = [d for d in listing.documents if not d.is_amendment]

download = client.download_document(originals[0].document_id)
# download.content is the submission ZIP exactly as received;
# listing/download carry retrieved_at and api_version for the manifest.
```

The client translates EDINET's body-level statuses — observed EDINET
API-level errors may be returned as HTTP 200 with the effective status in the
response body: an invalid subscription key raises
`EdinetAuthenticationError`, and an unknown docID raises
`DocumentNotFoundError`. Transport-level HTTP errors are handled separately:
real HTTP 429/5xx failures are retried before raising
`EdinetRateLimitError`/`EdinetTransportError`. The API key never appears in
URLs, logs, or exception messages.

The same retrieval is available from the CLI (the key is read only from
`EDINET_API_KEY`; there is deliberately no `--api-key` flag). Selection is
never implicit — with `--date` you either `--list-only` or name a `--select`
strategy, and the printed record keeps the full candidate set:

```console
$ edinet-replay fetch --date 2025-06-27 --edinet-code E04236 --list-only
$ edinet-replay fetch --date 2025-06-27 --edinet-code E04236 \
    --select latest-original-filing --store ./store
$ edinet-replay fetch --document-id S100W1NC --store ./store
```

## Planned scope

EDINET Replay is intended to:

- retrieve official filing packages through the EDINET API without requiring use of the Japanese-language website;
- preserve the byte-exact source package together with raw-package and normalized-content hashes;
- resolve XBRL and Inline XBRL using Arelle rather than reimplementing XBRL semantics;
- export faithful fact representations that retain contexts, units, dimensions, accuracy attributes, nil values, footnotes, and source provenance;
- provide traceable references from extracted facts to elements in the original filing package; and
- support reproducible extraction from explicitly selected and version-pinned inputs.

The retrieval and faithful-representation layers are designed not to depend on a specific accounting standard. Conformance claims for JP GAAP, IFRS, and U.S. GAAP start from the fixed packages in the [β corpus](corpus/); broader coverage is added only with new corpus entries and golden hashes.

## What this project does not do

EDINET Replay does not:

- merge different XBRL concepts into a presumed common economic concept;
- normalize, correct, or assert the economic meaning of reported facts;
- guarantee comparability across companies, periods, or accounting standards;
- provide investment recommendations or investment advice; or
- represent an official EDINET or Financial Services Agency product.

> EDINET Replay is an independent open-source project. It is not affiliated with, sponsored by, or endorsed by Japan's Financial Services Agency.

## Design

Two layers, deliberately separated:

- **Layer 1 — faithful reproduction (this project, OSS):** retrieval, package handling, provenance, and OIM-compatible faithful facts.
- **Layer 2 — interpretation (out of scope here):** concept mapping, normalization, comparability / computability assessment. These carry research judgment and belong in separate, downstream layers.

The project defines the inputs and canonicalization rules required to test whether an extraction can be reproduced: source content hash + taxonomy package hash + Arelle version + extractor version + schema version + an explicit document-selection record. See [architecture](docs/architecture.md) · [reproducibility](docs/reproducibility.md) · [schema](docs/schema.md).

## Engine

XBRL / Inline XBRL semantics are intended to be resolved by [Arelle](https://arelle.org/) (Apache-2.0, XBRL International certified). EDINET Replay does not reimplement context, dimension, unit, or accuracy resolution — it is designed to map Arelle's model to a faithful, provenance-preserving JSON and add EDINET-specific source references.

## Documentation

- [For researchers](docs/for-researchers.md)
- [For investors / data teams](docs/for-investors.md)
- [Working with Japanese market data](docs/japanese-market-data.md)
- 日本語: [README.ja.md](README.ja.md)

## Maintenance

EDINET Replay is a pre-alpha project maintained on a best-effort basis. There is
no guaranteed response time for issues or pull requests, and opening one does not
guarantee a change will be accepted. Please discuss large changes in an issue
first, and report security vulnerabilities privately (see [SECURITY.md](SECURITY.md)),
not in public issues. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Citation

If you use EDINET Replay in research, please cite it — see [CITATION.cff](CITATION.cff).
