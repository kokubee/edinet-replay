# Taxonomy pins

This directory holds **pin records only** — one JSON per pinned EDINET taxonomy
distribution. The taxonomy bodies themselves are large, externally distributed,
and must not be committed; they are stored outside the repo under
`~/.cache/edinet-replay/taxonomies/` and registered into
`~/.cache/edinet-replay/registry/` via `edinet_replay.taxonomy.register`.

Each pin record fixes the reproduction identity of a taxonomy: `source_url`,
`downloaded_at`, `file_size`, `raw_sha256` (byte-exact distribution), and
`content_sha256` (normalized contents, `entry-path-and-content-sha256-v1`). The
`content_sha256` is what a manifest's `taxonomy_package` references.

`required_for` lists the taxonomy series a filing needs; it is only asserted
after an offline-resolution test confirms the pinned package resolves them
(see `offline_config` / the Arelle offline-resolution test).

Note: the FSA distribution `1c_Taxonomy.zip` is a plain directory tree
(`タクソノミ/taxonomy/...`), **not** a standard Taxonomy Package (no
`META-INF/taxonomyPackage.xml` / catalog), so offline URL resolution is wired
separately rather than via a package catalog.
