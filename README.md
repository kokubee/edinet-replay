# EDINET Replay

Toward reproducible, verifiable access to Japan's EDINET corporate disclosures — currently at the schema-and-specification stage.

EDINET Replay is an open-source project for developing a reproducible, provenance-preserving extraction workflow for Japan's EDINET corporate filings.

It defines versioned schemas and reproducibility contracts for preserving official filing packages, resolving XBRL and Inline XBRL through [Arelle](https://arelle.org/), and producing machine-readable representations that remain traceable to their source filings.

The project is designed for **data engineers, quantitative researchers, XBRL implementers, ESG data users, academic researchers, financial data providers, and the data teams of institutional investors** who need verifiable access to Japanese corporate disclosures. General retail investors are unlikely to use it directly.

> **Project status: pre-alpha.** EDINET Replay currently provides versioned JSON Schemas, reproducibility specifications, and validation fixtures. The extraction client and Arelle-based implementation are under development and are not production-ready.

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

## Planned scope

EDINET Replay is intended to:

- retrieve official filing packages through the EDINET API without requiring use of the Japanese-language website;
- preserve the byte-exact source package together with raw-package and normalized-content hashes;
- resolve XBRL and Inline XBRL using Arelle rather than reimplementing XBRL semantics;
- export faithful fact representations that retain contexts, units, dimensions, accuracy attributes, nil values, footnotes, and source provenance;
- provide traceable references from extracted facts to elements in the original filing package; and
- support reproducible extraction from explicitly selected and version-pinned inputs.

The retrieval and faithful-representation layers are designed not to depend on a specific accounting standard. Support claims for particular JP GAAP, IFRS, or U.S. GAAP filing patterns will be documented only after they are covered by conformance fixtures and regression tests.

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
