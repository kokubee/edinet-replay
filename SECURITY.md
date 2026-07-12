# Security Policy

## Reporting a vulnerability

Please do **not** open a public issue for security problems. Report them
privately to the maintainer (see `CITATION.cff` / the repository owner's contact)
so a fix can be prepared before disclosure.

## EDINET API keys

EDINET access requires a subscription key issued by Japan's Financial Services
Agency. Handle it carefully:

- **Never** post an API key in an issue, pull request, commit, log, fixture, or
  test. Keys belong only in the `EDINET_API_KEY` environment variable (or a
  git-ignored `.env`).
- The library reads the key from `EDINET_API_KEY` and **never** writes it into
  outputs, manifests, faithful-filing documents, or logs. Keep it that way in any
  contribution.
- If a key is exposed, **regenerate it on the EDINET dashboard** — regeneration
  is what invalidates the leaked key. A key committed to a private repository is
  still compromised; rotate it.
- **Do not judge authentication by HTTP status alone.** The EDINET API returns
  **HTTP 200 even for an invalid key** and puts the real result in the response
  body's `StatusCode` (an invalid key yields `{"StatusCode": 401, "message":
  "...invalid subscription key..."}`). Always check the body when verifying a
  key's validity — a 200 does not mean the key worked.

## Reproduction artifacts

Extraction manifests and faithful-filing outputs are designed to contain no
secrets. Do not add fields that could carry a key, and do not commit real
filing data, taxonomy archives, caches, or `.env` files.
