# Working with Japanese market data

Notes for people who have not worked with EDINET or Japanese XBRL before.

## EDINET in one paragraph

EDINET is Japan's statutory electronic disclosure system, operated by the
Financial Services Agency (FSA) — broadly comparable to the U.S. SEC's EDGAR.
Filings are retrieved as packages (ZIP) via the EDINET API v2 and contain XBRL
and, increasingly, Inline XBRL documents.

## Things that trip people up

- **Company-specific extension tags.** Japanese filings extend the standard
  taxonomy heavily. Reading only standard tags loses data.
- **Taxonomy versions change yearly.** The taxonomy (DTS) is part of the input;
  the same document resolved against a different taxonomy can differ. EDINET
  Replay pins the taxonomy package by hash and resolves offline.
- **Inline XBRL numeric transforms.** Presented text, lexical value, and the
  transform (`@scale`, `@sign`, `@format`) differ from the resolved value.
  EDINET Replay keeps all layers.
- **Correction and re-filing.** "The latest annual report" is ambiguous; the
  selection step is explicit and recorded, never implicit.
- **Google-News-style opaque intermediaries do not apply here** — EDINET is the
  primary source, but its metadata and site are Japanese-first, which is part of
  what this toolkit removes as a barrier.

## Access

You need an EDINET API key (issued by the FSA). Provide it via environment
variable or config; it is never written into outputs or manifests.
