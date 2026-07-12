# Canonicalization profiles

Two independent profiles, both named in every faithful-filing document under
`canonicalization`.

## `faithful-filing-jcs-v1` (JSON)

Makes a faithful-filing document byte-reproducible so it can be hashed
(golden-by-hash). Aligned with RFC 8785 (JCS), with one deliberate deviation:
significant values are carried as JSON strings, so JCS's number-serialization
rules never apply to them.

Rules:

1. Encoding is UTF-8.
2. No Unicode normalization is applied (NFC/NFD left exactly as parsed).
3. Object keys are sorted by Unicode code point.
4. No insignificant whitespace; no trailing newline.
5. Numbers that carry meaning (fact values, decimals, precision, scale-derived
   values) are strings, not JSON numbers, to preserve big integers, precision,
   and exponents. The only JSON numbers that appear are structural integers
   defined by the schema (e.g. `line`, `column`, `ixbrl_transform.scale`).
6. Map containers (`facts`, `contexts`, `units`, `footnotes`) are ordered by
   their id (which is the map key), consistent with rule 3.
7. Array order is fixed by the schema, not by input order:
   - `fact_footnote_relationships`: sorted by `(fact_id, footnote_id, arcrole)`.
   - `unit.numerator` / `unit.denominator`: original measure order preserved
     (order is semantically significant for units).
   - `explicit_dimensions` / `typed_dimensions` are maps, ordered by rule 3.

## `xml-c14n-1.1-without-comments` (XML)

Applied to a typed-dimension member's XML before hashing it into
`typed_dimensions.<axis>.canonical_xml_sha256`. Uses the W3C Canonical XML 1.1
(omit comments) algorithm so that differences in namespace prefixes, attribute
order, or insignificant whitespace do not change the hash, while the verbatim
member is still preserved in the sibling `xml` field.
