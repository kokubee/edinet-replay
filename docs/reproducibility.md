# Reproducibility

A faithful extraction is reproducible **iff** the following are all fixed:

```
source content_sha256
+ taxonomy package content_sha256
+ Arelle version
+ extractor version
+ faithful-filing schema version
+ explicit selection record
= reproducible extraction identity
```

Timestamps (`retrieved_at`, `generated_at`) and tool `extensions` are provenance
only and belong to **no** identity.

## Two identities, kept separate

- **Selection identity** — given the same candidate set, was the same document
  chosen? = f(selector name/version, sorted candidate ids, selected id,
  selection parameters).
- **Extraction identity** — given the same document, is the same faithful JSON
  produced? = f(source `content_sha256`, taxonomy `content_sha256`, Arelle
  version, extractor version, faithful-filing schema version,
  `extraction.configuration`).

## Dual hashing

Every hashable input is stored twice:

- `raw_sha256` — the received artifact, byte-exact (evidence / corruption / re-fetch diff).
- `content_sha256` — the normalized logical contents, stable across recompression.
  Algorithm is pinned: [`entry-path-and-content-sha256-v1`](content-hash-v1.md).

The **content** hash is the substantive input to extraction identity; the **raw**
hash preserves evidence of exactly what was received.

## Taxonomy is part of the input

The DTS (discoverable taxonomy set) determines how facts resolve. It is pinned by
hash and resolved **offline** from a vendored package; online resolution is
disallowed because a change to a remote taxonomy URL would silently alter output.

## Canonicalization

To make a faithful-filing document itself hashable (golden-by-hash), it is
serialized under [`faithful-filing-jcs-v1`](canonicalization-v1.md); typed
dimension XML is hashed under `xml-c14n-1.1-without-comments`.

See the schemas: [`schemas/extraction-manifest-1.0.0.schema.json`](../schemas/extraction-manifest-1.0.0.schema.json),
[`schemas/faithful-filing-1.0.0.schema.json`](../schemas/faithful-filing-1.0.0.schema.json).
