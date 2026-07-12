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
