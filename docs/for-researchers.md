# For researchers

EDINET Replay is a **reproducible retrieval and faithful-reproduction base** for
research on Japanese corporate disclosure — machine readability, comparability,
and computability of filings.

## What it gives you

- The same input reproduces the same faithful output (pinned identity; see
  [reproducibility.md](reproducibility.md)).
- Every fact links back to the original element in the source package.
- Versioned output schemas you can cite, independent of the code version.
- Multi-standard coverage (JP GAAP / IFRS / US GAAP) through one retrieval base.

## What it deliberately leaves to you (and to downstream research)

Concept mapping, normalization, comparability/computability scoring, and any
economic interpretation are **out of scope** for Layer 1. Keeping these separate
is the point: the reproducible substrate is open, and interpretive contributions
are stated separately (and can be audited against the faithful facts).

## Citing

See [CITATION.cff](../CITATION.cff). Please also pin the schema versions and the
Arelle version you used; those, with the source and taxonomy content hashes, are
what make a result reproducible by others.
