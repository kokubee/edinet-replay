#!/usr/bin/env python3
"""Phase 1 Arelle observation probe — no schema mapping, no golden.

Loads an EDINET filing entry point through Arelle with the network BLOCKED
(webCache.workOffline = True), then reports what remote taxonomy URLs Arelle
would need but was refused, and inventories the model (facts / contexts / units /
footnotes and per-fact sourceline / @id / inline / typed-dim availability). This
is investigation only; it neither writes faithful JSON nor asserts a golden.

Usage: python tools/arelle_probe.py <entry-point-file>
"""
from __future__ import annotations

import re
import sys
from collections import Counter

from arelle import Cntlr, XbrlConst

_URL = re.compile(r"https?://[^\s'\"<>]+")
_MISS = ("offline", "unable to", "not loadable", "cannot", "no such", "failed to load")


def main(path: str) -> None:
    cntlr = Cntlr.Cntlr(logFileName="logToBuffer")
    cntlr.webCache.workOffline = True  # block network; record unmet references
    model = cntlr.modelManager.load(path)
    if model is None:
        print("load returned None")
        return

    facts = list(model.facts)
    print(f"entry:    {path}")
    print(f"facts:    {len(facts)}")
    print(f"contexts: {len(model.contexts)}")
    print(f"units:    {len(model.units)}")
    fn = model.relationshipSet(XbrlConst.factFootnote)
    print(f"footnote relationships: {len(fn.modelRelationships) if fn else 0}")

    # missing remote references (offline)
    missing: set[str] = set()
    levels: Counter = Counter()
    for rec in getattr(cntlr.logHandler, "logRecordBuffer", []):
        levels[rec.levelname] += 1
        msg = rec.getMessage()
        if any(k in msg.lower() for k in _MISS):
            missing.update(_URL.findall(msg))
    print(f"\nlog levels: {dict(levels)}")
    print(f"distinct missing remote URLs: {len(missing)}")
    for u in sorted(missing)[:30]:
        print("  ", u)

    # per-fact capability tallies
    with_line = with_id = inline = typed = explicit = 0
    for f in facts:
        if getattr(f, "sourceline", None):
            with_line += 1
        if f.get("id"):
            with_id += 1
        if type(f).__name__ == "ModelInlineFact":
            inline += 1
        ctx = f.context
        if ctx is not None and getattr(ctx, "qnameDims", None):
            if any(d.isExplicit for d in ctx.qnameDims.values()):
                explicit += 1
            if any(d.isTyped for d in ctx.qnameDims.values()):
                typed += 1
    n = len(facts) or 1
    print(f"\nfacts with sourceline: {with_line}/{n}")
    print(f"facts with @id:        {with_id}/{n}")
    print(f"inline facts:          {inline}/{n}")
    print(f"facts w/ explicit dim: {explicit}")
    print(f"facts w/ typed dim:    {typed}")

    # one detailed sample (prefer an inline numeric fact, else any numeric)
    numeric = next((f for f in facts if f.isNumeric and f.context is not None), None)
    fallback = numeric if numeric is not None else (facts[0] if facts else None)
    sample = next(
        (f for f in facts if type(f).__name__ == "ModelInlineFact" and f.isNumeric),
        fallback,
    )
    if sample is not None:
        c, u = sample.context, sample.unit
        print("\nsample fact:")
        print("  concept:   ", sample.qname)
        print("  value:     ", (sample.value or "")[:60])
        print("  decimals:  ", sample.decimals)
        print("  nil:       ", sample.isNil)
        print("  xml:lang:  ", sample.get("{http://www.w3.org/XML/1998/namespace}lang"))
        print("  sourceline:", getattr(sample, "sourceline", None))
        print("  @id:       ", sample.get("id"))
        print("  context id:", c.id if c is not None else None)
        print("  unit id:   ", u.id if u is not None else None)
        if u is not None:
            num = [str(m) for m in u.measures[0]]
            den = [str(m) for m in u.measures[1]]
            print("  unit measures:", num, "/", den)
        if type(sample).__name__ == "ModelInlineFact":
            print("  [inline] format:", sample.format)
            print("  [inline] scale: ", getattr(sample, "scale", None))
            print("  [inline] sign:  ", getattr(sample, "sign", None))
            print("  [inline] lexical (elementText):", (sample.textValue or "")[:40])


if __name__ == "__main__":
    main(sys.argv[1])
