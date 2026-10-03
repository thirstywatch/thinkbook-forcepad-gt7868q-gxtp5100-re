#!/usr/bin/env python3
"""Characterise the touchpad and force-sensor firmware images.

These two capsules are structurally identical to the haptic one (same FMP/MSS1/
SAML/CFU/Component layering, same two byte-identical offers) but their bodies
carry no download-block table and almost no strings. This script establishes
what they *do* have, so the difference between "opaque code image" and "data
table" is measured rather than asserted:

  * capsule geometry compared side by side with the haptic capsule
  * whether a block-table header is present at all
  * entropy profile -> code-like vs data-like
  * string census with the real (non-noise) matches separated from coincidences
  * byte-frequency and 4-byte-aligned word statistics
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

IMAGES = (
    ("SurfaceTouchpad_4.12.139", "触摸板主固件"),
    ("SurfaceTouchpadForce_10.0.156", "压感 Force Sensor 固件"),
    ("SurfaceTouchpadHaptic_2.9.139", "CS40L25 触觉 DSP 固件"),
)

# A string counts as a real hit only if it is a recognisable identifier, not a
# coincidental run of printable bytes inside binary data.
IDENTIFIER = re.compile(
    r"^(?:[A-Z][A-Z0-9_]{3,}|[A-Za-z]+(?:[A-Z][a-z]+){1,}[A-Za-z]*|"
    r"[a-z]+_[a-z_]+|[A-Z][a-z]+[A-Z][A-Za-z]*)$")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    c = Counter(data)
    n = len(data)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def block_table_header(body: bytes) -> dict:
    """The haptic body starts with revision=0x02800010 and a plausible count."""
    if len(body) < 8:
        return dict(present=False)
    rev, count = struct.unpack_from("<II", body, 0)
    ok = rev == 0x02800010 and 0 < count < 4096
    return dict(present=bool(ok), revision=f"0x{rev:08X}", count=count)


def window_entropy(body: bytes, window: int = 2048) -> list[dict]:
    out = []
    for off in range(0, len(body), window):
        chunk = body[off:off + window]
        out.append(dict(offset=f"0x{off:05X}", entropy=round(entropy(chunk), 3)))
    return out


def string_census(body: bytes, min_len: int = 6) -> dict:
    runs = [m.group().decode("ascii")
            for m in re.finditer(rb"[\x20-\x7e]{%d,}" % min_len, body)]
    real = [s for s in runs if IDENTIFIER.match(s)]
    return dict(total=len(runs), identifier_like=len(real), sample=real[:20])


def word_stats(body: bytes) -> dict:
    """4-byte-aligned u32 distribution: tables have many small values, code does not."""
    n = len(body) // 4
    words = [struct.unpack_from("<I", body, i * 4)[0] for i in range(n)]
    small = sum(1 for w in words if w < 0x1000)
    zero = sum(1 for w in words if w == 0)
    ff = sum(1 for w in words if w == 0xFFFFFFFF)
    return dict(aligned_words=n,
                below_0x1000=round(small / n, 4) if n else None,
                zero_ratio=round(zero / n, 4) if n else None,
                all_ones_ratio=round(ff / n, 4) if n else None)


def main():
    out = []
    for stem, title in IMAGES:
        d = OUT / stem
        body = (d / "body_0.bin").read_bytes()
        comp = (d / "component_0.bin").read_bytes()
        rep = json.load(open(d / "report.json", encoding="utf-8"))
        v = rep["variants"][0]

        hdr = block_table_header(body)
        prof = window_entropy(body)
        census = string_census(body)
        ws = word_stats(body)
        hi = sum(1 for p in prof if p["entropy"] >= 7.0)

        print(f"=== {title}  ({stem})")
        print(f"  capsule  {rep['meta']['capsule_size']:,} B   "
              f"flags {rep['meta']['capsule_flags']}   mss1 {rep['meta']['mss1_version']}")
        print(f"  offer    {v['offer']}  (two byte-identical payloads: "
              f"{rep['variants'][0]['component_sha256'] == rep['variants'][1]['component_sha256']})")
        print(f"  CFU      {v['cfu_records']:,} records -> component {v['component_bytes']:,} B"
              f"  body@{v['body_offset']}  {v['body_size']:,} B")
        print(f"  body sha {sha(body)[:32]}")
        print(f"  download-block header present: {hdr['present']}"
              + (f"  revision {hdr['revision']} count {hdr['count']}" if hdr["present"] else ""))
        print(f"  entropy  {entropy(body):.3f} bits/byte   "
              f"code-like windows {hi}/{len(prof)} (>=7.0)")
        print(f"  strings  {census['total']} runs >=6 chars, "
              f"{census['identifier_like']} identifier-like")
        if census["sample"]:
            print(f"    {census['sample'][:10]}")
        print(f"  u32      below 0x1000 {ws['below_0x1000']:.1%}   "
              f"zero {ws['zero_ratio']:.1%}   all-ones {ws['all_ones_ratio']:.1%}")
        print()

        out.append(dict(stem=stem, title=title,
                        capsule=rep["meta"], variant=v,
                        body_sha256=sha(body), component_sha256=sha(comp),
                        block_table_header=hdr,
                        entropy=round(entropy(body), 4),
                        code_like_windows=hi, window_count=len(prof),
                        entropy_profile=prof,
                        strings=census, u32_stats=ws))

    (HERE / "touchpad_form_report.json").write_text(json.dumps(out, indent=1),
                                                    encoding="utf-8")


if __name__ == "__main__":
    main()
