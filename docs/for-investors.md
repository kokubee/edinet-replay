# For investors and data teams

> This project is a **data-audit foundation, not an investment tool.** It gives
> you verifiable access to what companies actually filed; it does not tell you
> what to buy.

## Why EDINET matters for Japanese-equity analysis

EDINET is where Japanese issuers file statutory disclosures (annual securities
reports and more). If you analyze Japanese equities from primary sources, EDINET
is the primary source.

## How EDINET differs from EDGAR

- The interface and metadata are Japanese-first.
- Filings make heavy use of **company-specific extension tags** on top of the
  standard taxonomy, so naive tag reading undercounts or misreads data.
- Inline XBRL, dimensions, and taxonomy-version changes are common.

## Why a normalized database is not enough

A vendor that maps every issuer onto one set of "comparable" metrics is already
making **interpretive judgments** — which extension tag maps to which standard
concept, how accounting-standard differences were absorbed, what was dropped.
Comparability is not automatically guaranteed by normalization; it is a claim
that should be explainable against the original facts.

EDINET Replay gives you the **audit surface** for that: the faithful, source-
linked facts a normalized value should be reconcilable to.

## What you can do with it

- Reconcile a data provider's API value against the original XBRL fact.
- Detect definition changes across fiscal years.
- Inspect company-specific extension tags directly.
- Build reproducible research datasets with provenance.

It does not provide investment advice, and it is not affiliated with the FSA.
