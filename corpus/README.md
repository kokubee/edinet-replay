# β corpus

A small, comparable set of **real EDINET annual reports** used as the public
conformance surface for EDINET Replay.

This is not a financial database. Each entry pins:

- an official EDINET `document_id`
- dual package hashes (`raw_sha256` + `content_sha256`)
- a pinned FSA taxonomy distribution (identifier + dual hashes)
- the expected **canonical** faithful-filing hash and size

Anyone with the official ZIP and the matching taxonomy zip can regenerate the
faithful JSON and check it against the committed expectation. Source packages
and taxonomy bodies are **not** in this repository (license / size); obtain them
from EDINET and the FSA taxonomy download pages, guided by the pin records in
[`taxonomies/`](../taxonomies/).

## Coverage (beta-v1)

| Standard | EDINET | docID | Period end | Taxonomy pin | Facts |
|----------|--------|-------|------------|--------------|------:|
| JP GAAP  | E04236 | S100W1NC | 2025-03-31 | edinet-fsa-2024-11-01 | 2590 |
| IFRS     | E00492 | S100VH9B | 2024-12-31 | edinet-fsa-2023-12-01 | 2207 |
| US GAAP  | E01532 | S100VXAI | 2025-03-31 | edinet-fsa-2024-11-01 | 1225 |

The IFRS entry deliberately uses the **previous** FSA taxonomy edition so the
corpus exercises taxonomy-year difference as well as accounting-standard
difference. Full machine-readable index: [`beta-v1/catalog.json`](beta-v1/catalog.json).
Expected canonical outputs live under [`tests/golden/`](../tests/golden/) (shared
with the golden regression suite).

## Reproduce one entry

```console
# 1. Pin the taxonomy (download from the pin's source_url; verify hashes)
#    taxonomies/edinet-fsa-2024-11-01.json → ~/.cache/edinet-replay/taxonomies/.../1c_Taxonomy.zip

# 2. Fetch the official package (EDINET_API_KEY from the environment only)
edinet-replay fetch --document-id S100W1NC --store ./store

# 3. Extract offline against the pin
edinet-replay extract ./store/packages/S100W1NC/<raw_sha256>.zip \
  --taxonomy edinet-fsa-2024-11-01 -o ./out

# 4. Validate schemas
edinet-replay validate filing ./out/faithful-filing.json
edinet-replay validate manifest ./out/extraction-manifest.json
```

Compare the canonicalization of `faithful-filing.json` to
`tests/golden/<edinet>-<docID>.canonical.json.gz` (see
`docs/canonicalization-v1.md`). The golden suite does this automatically when
`EDINET_REPLAY_TEST_FILINGS` points at a local cache of the source packages.

## Non-goals

- No normalized financial metrics, scores, or “comparable” line items
- No investment recommendations
- No claim that three filings prove universal multi-GAAP support — only that
  these three **documented** packages regenerate under the pinned identity

## Adding an entry

1. Choose a fixed original (non-amendment) annual report `document_id`.
2. Record package dual hashes and the taxonomy pin that resolves its DTS offline.
3. Run `extract.extract_package` twice in isolated caches; require byte-identical
   canonical output.
4. Commit `tests/golden/<E>-<docID>.json` + `.canonical.json.gz` (gzip `mtime=0`).
5. Append the entry to `corpus/beta-v1/catalog.json` and a golden test module.
6. Explain any golden hash change in the PR (bug fix / Arelle / taxonomy /
   non-determinism) — unexplained golden updates are not accepted.
