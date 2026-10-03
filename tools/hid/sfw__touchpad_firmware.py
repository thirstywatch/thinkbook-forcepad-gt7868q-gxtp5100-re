#!/usr/bin/env python3
"""Characterise the three non-haptic Surface touchpad firmware images.

The Haptic capsule is a CS40L25 download-block table and is handled elsewhere.
The other two are opaque: the project notes only record their sizes and that
their strings survive CFU de-framing. This script establishes what can actually
be said about each one, and is explicit where the answer is "structure only, no
semantics recovered".

For each: capsule/offer geometry, component header, body hash, string census
with the touchpad/haptic vocabulary called out, and an entropy profile that
distinguishes code-like from data-like regions.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import struct
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"

TOUCHPAD_VOCAB = (
    "touchpad", "trackpad", "touch", "force", "pressure", "pen", "digitizer",
    "button", "gesture", "hid", "ptp", "precision", "i2c", "spi", "irq",
    "gpio", "reset", "firmware", "fw", "update", "capsule", "config",
    "report", "descriptor", "sensor", "baseline", "noise", "threshold",
    "scan", "rate", "resolution", "left", "right", "center",
)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    c = Counter(data)
    n = len(data)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def region_entropy(body: bytes, window: int = 4096) -> list[dict]:
    """Entropy per window: separates code (mid-high, structured) from tables."""
    out = []
    for off in range(0, len(body), window):
        chunk = body[off:off + window]
        out.append(dict(offset=f"0x{off:05X}", bytes=len(chunk),
                        entropy=round(entropy(chunk), 3)))
    return out


def strings_of(body: bytes, min_len: int = 5) -> list[dict]:
    return [dict(offset=f"0x{m.start():05X}", text=m.group().decode("ascii"))
            for m in re.finditer(rb"[\x20-\x7e]{%d,}" % min_len, body)]


def vocab_hits(strings: list[dict]) -> list[dict]:
    out = []
    for s in strings:
        low = s["text"].lower()
        tags = sorted({v for v in TOUCHPAD_VOCAB if v in low})
        if tags:
            out.append(dict(**s, tags=tags))
    return out


def head_field(data: bytes) -> dict:
    """First 64 bytes read as a mix of u32le and ASCII, for orientation."""
    return dict(head64=data[:64].hex(),
                u32le=[struct.unpack_from("<I", data, i)[0] for i in range(0, 32, 4)],
                ascii="".join(chr(c) if 32 <= c < 127 else "." for c in data[:64]))


def analyse(stem: str, title: str) -> dict:
    d = OUT / stem
    report = d / "report.json"
    base = json.load(open(report, encoding="utf-8")) if report.exists() else {}
    body = (d / "body_0.bin").read_bytes()
    comp = (d / "component_0.bin").read_bytes()
    strs = strings_of(body)
    vocab = vocab_hits(strs)

    print(f"=== {title}")
    print(f"  body {len(body):,} B  sha {sha(body)[:16]}  entropy {entropy(body):.3f}")
    if base.get("variants"):
        v = base["variants"][0]
        print(f"  component {v['component_bytes']:,} B  body@{v['body_offset']}  "
              f"cfu records {v['cfu_records']}")
        print(f"  offer {v['offer']}")
    print(f"  strings {len(strs)}  printable "
          f"{sum(len(s['text']) for s in strs)/len(body):.2%}")
    print(f"  touchpad-vocabulary hits {len(vocab)}")
    for s in vocab[:14]:
        print(f"    {s['offset']}  {s['text'][:66]}")
    print("  head:")
    hf = head_field(body)
    print(f"    u32le {hf['u32le']}")
    print(f"    ascii {hf['ascii']!r}")
    prof = region_entropy(body)
    hi = [p for p in prof if p["entropy"] >= 7.0]
    print(f"  entropy profile: {len(prof)} windows, {len(hi)} at >=7.0 bits/byte "
          f"(code-like), min {min(p['entropy'] for p in prof):.2f}, "
          f"max {max(p['entropy'] for p in prof):.2f}")
    print()

    return dict(title=title, body_bytes=len(body), body_sha256=sha(body),
                component_bytes=len(comp), component_sha256=sha(comp),
                entropy=round(entropy(body), 4),
                capsule=base.get("meta", {}), variant=base.get("variants", [{}])[0]
                if base.get("variants") else {},
                string_count=len(strs),
                printable_ratio=round(sum(len(s["text"]) for s in strs) / len(body), 4),
                vocabulary_hits=vocab, head=hf, entropy_profile=prof,
                strings=strs)


def main():
    out = []
    for stem, title in (
        ("SurfaceTouchpad_4.12.139", "SurfaceTouchpad 4.12.139 (touchpad main firmware)"),
        ("SurfaceTouchpadForce_10.0.156", "SurfaceTouchpadForce 10.0.156 (force sensor)"),
        ("SurfaceTouchpadHaptic_2.9.139", "SurfaceTouchpadHaptic 2.9.139 (CS40L25 DSP)"),
    ):
        if (OUT / stem / "body_0.bin").exists():
            out.append(analyse(stem, title))
    (HERE / "touchpad_firmware_report.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
