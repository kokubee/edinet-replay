# EDINET Replay

A reproducible, provenance-preserving extraction toolkit for Japan's EDINET corporate filings.

EDINET Replay downloads official filing packages from Japan's Financial Services Agency (FSA), preserves the original source artifacts, resolves XBRL and Inline XBRL through [Arelle](https://arelle.org/), and exports a faithful, machine-readable representation with traceable links back to the source filing.

The project is designed for **data engineers, quantitative researchers, XBRL implementers, ESG data users, academic researchers, financial data providers, and the data teams of institutional investors** who need verifiable access to Japanese corporate disclosures. General retail investors are unlikely to use it directly.

> **Status: early.** The output *contracts* are defined first — as versioned JSON Schemas in [`schemas/`](schemas/) — before the extractor is built. See [docs/reproducibility.md](docs/reproducibility.md).

## What is EDINET?

EDINET is Japan's statutory electronic disclosure system, operated by the Financial Services Agency (FSA). It is broadly comparable to the U.S. SEC's EDGAR system.

## Why this project exists

EDINET filings are publicly available, but reproducible use remains difficult because:

- filing packages contain complex XBRL and Inline XBRL structures;
- taxonomy versions change over time;
- extracted values may lose context, units, dimensions, or source provenance;
- normalized financial databases often do not disclose how original facts were transformed.

EDINET Replay focuses on **faithful reproduction rather than financial interpretation.** It preserves the source facts first. Mapping, normalization, comparability assessment, and investment analysis belong in separate downstream layers.

## What it does

- Retrieve filing packages from EDINET without operating the Japanese-language site
- Preserve the raw package (byte-exact) and record both its raw and normalized-content hashes
- Resolve XBRL / Inline XBRL through Arelle — without reimplementing XBRL semantics
- Export faithful facts with contexts, units, dimensions, decimals/precision, nil, and footnotes intact
- Keep a traceable reference from every fact back to its source element in the package
- Handle JP GAAP, IFRS, and US GAAP filings through the same retrieval base
- Make each extraction reproducible: the same pinned inputs produce the same output

## What it does NOT do

This boundary is intentional:

- It does **not** automatically merge different tags into one "same" concept
- It does **not** normalize or assert the economic meaning of data
- It does **not** provide investment advice
- It is **not** an official product of EDINET or the FSA

> This project is not affiliated with or endorsed by Japan's Financial Services Agency.

## Design

Two layers, deliberately separated:

- **Layer 1 — faithful reproduction (this project, OSS):** retrieval, package handling, provenance, and OIM-compatible faithful facts.
- **Layer 2 — interpretation (out of scope here):** concept mapping, normalization, comparability / computability assessment. These carry research judgment and belong in separate, downstream layers.

Reproduction identity is fixed by: source content hash + taxonomy package hash + Arelle version + extractor version + schema version + an explicit document-selection record. See [architecture](docs/architecture.md) · [reproducibility](docs/reproducibility.md) · [schema](docs/schema.md).

## Engine

XBRL / Inline XBRL semantics are resolved by [Arelle](https://arelle.org/) (Apache-2.0, XBRL International certified). EDINET Replay does not reimplement context, dimension, unit, or decimals resolution — it maps Arelle's model to a faithful, provenance-preserving JSON and adds EDINET-specific source references.

## Documentation

- [For researchers](docs/for-researchers.md)
- [For investors / data teams](docs/for-investors.md)
- [Working with Japanese market data](docs/japanese-market-data.md)
- 日本語: [README.ja.md](README.ja.md)

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Citation

If you use EDINET Replay in research, please cite it — see [CITATION.cff](CITATION.cff).

## Commercial services

The open-source project covers retrieval, faithful reproduction, and provenance. Commercial services may include managed historical datasets, extraction audits, taxonomy migration analysis, normalized disclosure datasets, and enterprise support.
