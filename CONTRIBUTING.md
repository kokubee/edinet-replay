# Contributing

EDINET Replay is pre-alpha. Contributions and issues are welcome; please read
[SECURITY.md](SECURITY.md) first (especially the API-key rules).

## Development setup

```
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"        # schema/unit tests + ruff + pytest
pip install -e ".[dev,xbrl]"   # also install Arelle for the extraction tests
```

Run the checks:

```
ruff check .
pytest
```

## Tests and test data

The unit / schema / semantic / canonicalization / fixture tests run anywhere and
need no external data. The **integration and golden-regression tests need real
EDINET filings and taxonomy packages, which are NOT committed** (they are large
and externally distributed). They skip automatically unless the data is present:

- Point `EDINET_REPLAY_TEST_FILINGS` at a directory holding
  `{edinetCode}/{docID}/XBRL/PublicDoc/...` filings.
- Place pinned FSA taxonomy packages under `~/.cache/edinet-replay/taxonomies/`
  (see the pin records in `taxonomies/`).

```
EDINET_REPLAY_TEST_FILINGS=/path/to/filings pytest
```

## Continuous integration

CI runs only the data-free tests (unit, schema, semantic, canonicalization,
fixtures) plus Ruff across Python 3.11–3.13. **Real-data golden regression is
intentionally not run in public CI** (no EDINET data is stored in the repo or the
runners); run it locally, or in a private CI with the data mounted.

## Rules of thumb

- Never commit `.env`, real filings, taxonomy ZIPs, caches, `.venv`, build
  outputs, absolute local paths, or API keys.
- Financial values stay strings; arrays keep producer order; object keys sort by
  code point (see `docs/canonicalization-v1.md`). Keep outputs deterministic — the
  golden tests regenerate from scratch and compare bytes.

## Before opening a pull request

Please **open an issue to discuss large or architectural changes before
implementing them.** Unsolicited large PRs may be closed without a full review.

A change may be declined even if it is technically fine — for example if it is
outside the project's scope, bypasses Arelle to reimplement XBRL semantics, loses
provenance, changes canonical output without justification, adds a heavy or
unclear dependency, or is more than can be maintained. "This is outside the
current maintenance scope" is a sufficient reason.

## What the maintainer checks

1. Is it in scope for `edinet-replay`?
2. No secrets / real EDINET keys / confidential data.
3. The contributor has the right to submit the code.
4. Tests are present and CI is green.
5. Does canonical output change? Does it break schema compatibility?
6. If a golden hash changes, is the reason explained (bug fix vs Arelle version
   vs taxonomy vs a determinism regression)? A golden update with no explanation
   is not accepted — the golden is the expected value, so the reason comes first.
7. Schema changes need: version-impact note, fixture update, semantic-validator
   update, and a migration note.
8. Can this realistically be maintained going forward?

Merges are squash-only; `main` is protected (CI required, owner approval, no
force-push).

## AI-assisted contributions

AI-assisted contributions are welcome, but the contributor remains responsible
for understanding, testing, and licensing the submitted code.

## Maintenance expectations

EDINET Replay is maintained on a best-effort basis.

There is no guaranteed response time for issues or pull requests. Opening an issue
or pull request does not guarantee that a proposed change will be accepted. Large
changes should be discussed in an issue before implementation. Security
vulnerabilities must not be reported in public issues (see
[SECURITY.md](SECURITY.md)).
