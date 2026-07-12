# content-hash algorithm `entry-path-and-content-sha256-v1`

Normalized, compression-independent hash of a ZIP archive's *logical contents*.
Used for `content_sha256` on both `source_package` and `taxonomy_package` in the
extraction manifest. It is stable across recompression and ZIP metadata changes,
so it is the substantive input to **extraction identity**. (The byte-exact
artifact hash is recorded separately as `raw_sha256`.)

## Algorithm

Given a ZIP archive:

1. Enumerate all file entries.
2. Exclude directory entries.
3. Normalize each entry path: convert separators to `/`, strip a leading `./`.
4. Reject the archive if any normalized path contains a `..` segment
   (path traversal / Zip Slip).
5. Do **not** change Unicode form or the case of file names.
6. For each file, compute the SHA-256 of its **uncompressed** bytes.
7. Sort entries by the UTF-8 byte order of the normalized path.
8. For each entry, build a record:

   ```
   UTF8(path) NUL ASCII(hex_file_sha256) LF
   ```

   i.e. `utf8(path) + b"\x00" + ascii(hex_digest) + b"\x0a"`.
9. `content_sha256 = SHA-256( concat(records) )`, lower-case hex.

Concatenating per-file hashes (not the file bytes) keeps the computation
diagnosable and bounded in memory for large packages, and lets the manifest's
`entries[]` inventory pinpoint which file changed when two `content_sha256`
values differ.

## Reference implementation (conceptual)

```python
import hashlib

def content_sha256_v1(files):
    # files: iterable of (raw_path: str, uncompressed_bytes: bytes), files only
    records = []
    normalized = []
    for raw_path, data in files:
        path = raw_path.replace("\\", "/")
        if path.startswith("./"):
            path = path[2:]
        if any(seg == ".." for seg in path.split("/")):
            raise ValueError(f"unsafe path: {raw_path}")
        normalized.append((path, hashlib.sha256(data).hexdigest()))
    for path, file_hash in sorted(normalized, key=lambda it: it[0].encode("utf-8")):
        records.append(
            path.encode("utf-8") + b"\x00" + file_hash.encode("ascii") + b"\x0a"
        )
    return hashlib.sha256(b"".join(records)).hexdigest()
```

## Notes

- Directory entries are excluded so that archives which differ only in whether
  they store explicit directory entries still hash equal.
- The NUL separator between path and hash prevents any ambiguity from paths that
  end in hex-like characters.
- Versioned: a future change to normalization or record framing ships as
  `entry-path-and-content-sha256-v2`; existing manifests remain interpretable via
  their pinned `content_hash_algorithm`.
