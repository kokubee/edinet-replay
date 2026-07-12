# Architecture

> Draft. Structure is fixed; module bodies are not yet implemented.

## Two layers

- **Layer 1 — faithful reproduction (this project, OSS).** Retrieval, package
  handling, provenance, and OIM-compatible faithful facts. No interpretation.
- **Layer 2 — interpretation (out of scope).** Concept mapping, normalization,
  comparability / computability assessment, master data. These carry research
  judgment and live in separate, downstream projects that *consume* Layer 1.

## Modules (Layer 1)

| Module     | Responsibility                                                        |
|------------|-----------------------------------------------------------------------|
| `client`   | EDINET API v2 communication only. No selection logic.                 |
| `catalog`  | Document lists, mechanical filters, candidate `docID` sets.           |
| `package`  | ZIP save, raw + content hashing, safe extraction (Zip Slip), inventory.|
| `taxonomy` | Register / hash-verify a pinned taxonomy package; offline resolution.  |
| `extract`  | Produce faithful JSON from Arelle's model; attach EDINET source refs.  |

Downstream consumers (examples): a GHG/sustainability extractor, a fundamentals
mapper, a sustainability-text extractor. These are **users** of Layer 1, not part
of it.

## Explicit selection boundary

The library helps *find* the latest annual report but never decides "what counts
as the latest" implicitly. Correction filings, resubmissions, and same-day
multiple filings make "latest" ambiguous, so selection is an explicit, named,
versioned step whose parameters and full candidate set are recorded.

```
documents = client.list_documents(date=...)             # faithful
candidates = catalog.filter(documents, edinet_code=..., document_type=...)  # mechanical
selected   = selectors.latest_original_filing(candidates)  # explicit policy
```
