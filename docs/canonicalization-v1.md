# Canonicalization profiles

Two independent profiles, both named in every faithful-filing document under
`canonicalization`.

## `edinet-replay-canonical-json-v1` (JSON)

Makes a faithful-filing document byte-reproducible so it can be hashed
(golden-by-hash).

> This profile is project-specific and does **not** claim full RFC 8785 (JCS)
> conformance. It is JCS-influenced, but financial values are carried as JSON
> strings (so JCS number rules never apply) and arrays follow the producer-order
> rule below. Promotion to a JCS-conformant name would require passing RFC 8785
> test vectors first.

Rules:

1. Encoding is UTF-8; no BOM.
2. No Unicode normalization is applied (NFC/NFD left exactly as parsed).
3. Duplicate object member names are rejected at parse time.
4. Object member names are sorted by Unicode code point.
5. No insignificant whitespace; strings escaped deterministically; no trailing newline.
6. Financial values (fact values, decimals, precision, iXBRL scale) are JSON
   **strings**, to preserve big integers, precision, and exponents. JSON booleans
   and null keep their native types. The only JSON numbers are structural
   integers defined by the schema (e.g. `line`, `column`, counts).
7. **Arrays preserve producer input order; canonicalization never re-sorts an
   array.** Determinism of array order is the producer's responsibility:
   - `fact_footnote_relationships`: the projector emits them sorted by
     `(fact_id, footnote_id, arcrole)`.
   - `candidate_document_ids`: the selector emits a deterministic order; it is a
     set with no ranking meaning, but canonicalization still preserves whatever
     order the selector produced (it does not re-sort here).
   - `unit.numerator` / `unit.denominator`: original measure order preserved
     (semantically significant).
   Only arrays a schema explicitly declares *unordered* may be sorted, and only
   by their declared comparison key.
8. Map containers (`facts`, `contexts`, `units`, `footnotes`, dimension maps) are
   JSON objects, so their member names sort under rule 4.

## `xml-c14n2` (XML)

Applied to a typed-dimension member's XML before hashing it into
`typed_dimensions.<axis>.canonical_xml_sha256`. Uses the W3C **Canonical XML 2.0**
algorithm with comments omitted (lxml's `c14n2` serialization) so that
differences in namespace prefixes, attribute order, or insignificant whitespace
do not change the hash, while the verbatim member is still preserved in the
sibling `xml` field.

> The profile name states exactly what is computed: lxml implements C14N 1.0 and
> C14N 2.0 but **not** C14N 1.1, so this project pins 2.0 rather than declaring an
> algorithm it does not run.
