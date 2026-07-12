# Schemas

The output contracts are versioned independently of the code, so the format can
become a stable reference even as the implementation evolves.

- [`extraction-manifest-1.0.0.schema.json`](../schemas/extraction-manifest-1.0.0.schema.json)
  — the reproduction identity of one extraction: source package (dual hash),
  explicit selection record, pinned taxonomy package, engine, extractor,
  extraction configuration. Contains no secrets.
- [`faithful-filing-1.0.0.schema.json`](../schemas/faithful-filing-1.0.0.schema.json)
  — OIM-compatible resolved facts plus provenance: original context/unit tables,
  iXBRL lexical/presentation layers, typed-dimension raw XML + canonical hash,
  footnote relationships, and per-fact EDINET package source references.

## Principles

- Numeric values are **strings** (preserve big integers, precision, exponents).
- `decimals` / `precision` are preserved **verbatim** (including `INF`); never computed.
- `nil` is distinct from an empty string and from an absent fact.
- Facts carry **resolved** aspects (`dimensions`) *and* **original** references
  (`source_context_ref` / `source_unit_ref`); the `contexts`/`units` tables keep
  the original structure.
- Every fact keeps a `source` pointer back into the package (`package_path`
  required; `element_id` / `line` optional, parser-dependent).

Supporting specs: [content-hash-v1.md](content-hash-v1.md) ·
[canonicalization-v1.md](canonicalization-v1.md).
