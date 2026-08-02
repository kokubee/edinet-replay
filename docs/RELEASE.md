# Release runbook (edinet-replay)

Owner: sole maintainer (presses `twine` or approves Trusted Publisher).

## Version lockstep (must match)

| Surface | Form |
|---------|------|
| `pyproject.toml` / `__version__` | PEP 440, e.g. `0.1.0b1` |
| Git tag / `CITATION.cff` / CHANGELOG heading | `0.1.0-beta.1` / `v0.1.0-beta.1` |

## Tag immutability

Never move a published tag. New content ⇒ **new version + new tag**.  
Yank only for severe breakage, with explicit maintainer approval; yank does not free the version slot for reuse.

## Build and inspect

From a **detached checkout of the release tag only**:

```bash
git fetch origin --tags
git switch --detach vX.Y.Z-…
rm -rf dist build src/*.egg-info
python -m pip install -U pip build twine check-wheel-contents
python -m build
python -m twine check --strict dist/*
check-wheel-contents dist/*.whl
shasum -a 256 dist/*   # record for provenance
```

Mandatory content scan (listings alone are not enough):

```bash
WHEEL_TMP=$(mktemp -d); SDIST_TMP=$(mktemp -d)
python -m zipfile -e dist/*-py3-none-any.whl "$WHEEL_TMP"
tar -xzf dist/*.tar.gz -C "$SDIST_TMP"
rg -n --text --no-ignore \
  -e '/Users/' -e '/home/[a-zA-Z]' -e '/Volumes/' \
  -e 'Subscription-Key' -e 'Ocp-Apim' \
  -e 'pypi-[A-Za-z0-9_]{20,}' \
  -e '-----BEGIN (RSA |OPENSSH )?PRIVATE KEY-----' \
  "$WHEEL_TMP" "$SDIST_TMP"
# Expect empty, or only documented allowlisted public header-name docs.
```

## Pin contract (0.1.0b1 and current beta)

- Schemas ship in the wheel (`edinet_replay/schemas/`).
- Taxonomy **pin JSON** is **not** in the wheel. For `extract`:

```bash
export EDINET_REPLAY_PINS_DIR=/path/to/repo/taxonomies
# or: edinet-replay extract … --pins-dir /path/to/repo/taxonomies
```

API: `edinet_replay.taxonomy.load_pin_record` / `prepare_offline_taxonomy`.  
FSA taxonomy ZIP bodies stay outside the package.

## Credentials

- Store tokens in env or keyring only: `TWINE_USERNAME=__token__`, `TWINE_PASSWORD=pypi-…`
- Never commit `.pypirc`, tokens, or `.env` with secrets.
- Prefer PyPI **Trusted Publisher** (GitHub OIDC) for later cuts after the project exists on PyPI.

## Publish order

1. **TestPyPI** (optional but preferred for first beta):

   ```bash
   python -m twine upload --repository testpypi dist/*
   ```

   Provenance install:

   ```bash
   python -m venv /tmp/edinet-testpypi
   /tmp/edinet-testpypi/bin/pip install -U pip
   /tmp/edinet-testpypi/bin/pip install "jsonschema>=4" "arelle-release>=2.36" "lxml>=4.9"
   /tmp/edinet-testpypi/bin/pip install -i https://test.pypi.org/simple/ --no-deps "edinet-replay==0.1.0b1"
   ```

2. **Production PyPI** (irreversible for that version):

   ```bash
   python -m twine upload dist/*
   pip install "edinet-replay[xbrl]==0.1.0b1"   # or --pre when defaulting latest
   ```

Prerelease note: plain `pip install edinet-replay` may skip betas; use `==0.1.0b1` or `--pre`.

## Do not

- Re-upload the same version
- Move tags after public consumers may have pinned them
- Package FSA taxonomy ZIP bodies
