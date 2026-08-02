#!/usr/bin/env python3
"""Render docs/assets/demo-extract.gif (README terminal demo).

Requires Pillow. Numbers are from the β corpus JP GAAP entry (E04236/S100W1NC).
Regenerate after intentional demo-copy changes::

    .venv/bin/python tools/render_demo_gif.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "demo-extract.gif"
W, H = 920, 520
BG = (18, 18, 22)
FG = (220, 223, 228)
DIM = (120, 124, 132)
GREEN = (80, 200, 120)
CYAN = (100, 200, 230)
YELLOW = (230, 190, 100)
WHITE = (255, 255, 255)
PROMPT = (140, 160, 200)

FONT_CANDIDATES = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Monaco.ttf",
    "/Library/Fonts/SF-Mono-Regular.otf",
    "/System/Library/Fonts/Supplemental/Courier New.ttf",
]


def _fonts():
    path = next((p for p in FONT_CANDIDATES if Path(p).exists()), None)
    if not path:
        f = ImageFont.load_default()
        return f, f
    try:
        return ImageFont.truetype(path, 15), ImageFont.truetype(path, 13)
    except OSError:
        f = ImageFont.load_default()
        return f, f


def new_frame(font_sm) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 28), fill=(32, 34, 40))
    d.ellipse((12, 8, 22, 18), fill=(255, 95, 86))
    d.ellipse((30, 8, 40, 18), fill=(255, 189, 46))
    d.ellipse((48, 8, 58, 18), fill=(39, 201, 63))
    d.text((72, 6), "edinet-replay — fetch → extract → validate", fill=DIM, font=font_sm)
    return im, d


def draw_lines(d, font, lines: list[tuple[str, tuple[int, int, int]]], start_y: int = 44):
    y = start_y
    for text, color in lines:
        max_chars = 100
        while text:
            chunk, text = text[:max_chars], text[max_chars:]
            d.text((16, y), chunk, fill=color, font=font)
            y += 20
        if y > H - 20:
            break


def main() -> None:
    font, font_sm = _fonts()
    scenes: list[list[tuple[str, tuple[int, int, int]]]] = []
    base = [
        ("# β demo — JP GAAP annual report  docID=S100W1NC  (Mitsui O.S.K. Lines)", DIM),
        ("", DIM),
    ]
    scenes.append(
        base
        + [
            ('$ pip install -e ".[xbrl]"', PROMPT),
            ("Successfully installed edinet-replay-0.1.0b1 arelle-release …", DIM),
        ]
    )
    scenes.append(
        scenes[-1]
        + [
            ("", DIM),
            ("$ export EDINET_API_KEY=…   # header auth only — never on the CLI", PROMPT),
            ("$ edinet-replay fetch --document-id S100W1NC --store ./store", PROMPT),
            ('{ "document_id": "S100W1NC",', FG),
            ('  "package": {', FG),
            ('    "raw_sha256": "36eabd861a97…",', FG),
            ('    "content_sha256": "cfee5f82993d…"', FG),
            ("  },", FG),
            ('  "selection": { "selected_by": "explicit_document" } }', FG),
        ]
    )
    scenes.append(
        scenes[-1]
        + [
            ("", DIM),
            ("$ edinet-replay extract ./store/packages/S100W1NC/36eabd….zip \\", PROMPT),
            ("    --taxonomy edinet-fsa-2024-11-01 -o ./out", PROMPT),
            ('{ "document_id": "S100W1NC",', FG),
            (
                '  "extraction_source": { "package_path": "XBRL/PublicDoc/jpcrp030000-….xbrl",',
                CYAN,
            ),
            ('                        "preferred_filename": true },', CYAN),
            ('  "filing": { "fact_count": 2590, "context_count": 347 },', GREEN),
            ('  "manifest": { "path": "./out/extraction-manifest.json" } }', FG),
        ]
    )
    scenes.append(
        scenes[-1]
        + [
            ("", DIM),
            ("$ edinet-replay validate filing  ./out/faithful-filing.json", PROMPT),
            ("OK: faithful-filing.json conforms to faithful-filing-1.0.0", GREEN),
            ("$ edinet-replay validate manifest ./out/extraction-manifest.json", PROMPT),
            ("OK: extraction-manifest.json conforms to extraction-manifest-1.0.0", GREEN),
        ]
    )
    scenes.append(
        [
            ("# same fact → back into the official ZIP", DIM),
            ("", DIM),
            ('$ jq \'.facts["fact-e059fbfab0e15ad3"]\' ./out/faithful-filing.json', PROMPT),
            ("{", FG),
            ('  "value": "4122148000000",', YELLOW),
            ('  "decimals": "-6",', FG),
            ('  "dimensions": {', FG),
            ('    "concept": "jppfs_cor:Assets",', FG),
            ('    "unit": { "numerator": ["iso4217:JPY"] }', FG),
            ("  },", FG),
            ('  "source": {', CYAN),
            (
                '    "package_path": "XBRL/PublicDoc/jpcrp030000-asr-001_E04236-….xbrl",',
                CYAN,
            ),
            ('    "line": 4943', GREEN),
            ("  }", CYAN),
            ("}", FG),
            ("", DIM),
            ("# source package, line 4943:", DIM),
            (
                '  <jppfs_cor:Assets contextRef="Prior1YearInstant" decimals="-6"',
                WHITE,
            ),
            ('                   unitRef="JPY">4122148000000</jppfs_cor:Assets>', WHITE),
            ("", DIM),
            ("# same value · same concept · same unit · line-level provenance", GREEN),
        ]
    )

    frames: list[Image.Image] = []
    durations: list[int] = []
    im0, d0 = new_frame(font_sm)
    draw_lines(
        d0,
        font,
        [
            ("EDINET Replay", WHITE),
            ("", DIM),
            ("Official EDINET ZIP  →  faithful JSON + manifest", FG),
            ("Pinned taxonomy · offline Arelle · line-level provenance", DIM),
            ("", DIM),
            ("JP GAAP · IFRS · US GAAP  β corpus", CYAN),
        ],
    )
    frames.append(im0)
    durations.append(1800)
    for i, lines in enumerate(scenes):
        im, d = new_frame(font_sm)
        draw_lines(d, font, lines)
        frames.append(im)
        durations.append(2200 if i < len(scenes) - 1 else 4000)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUT,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(frames)} frames)")


if __name__ == "__main__":
    main()
