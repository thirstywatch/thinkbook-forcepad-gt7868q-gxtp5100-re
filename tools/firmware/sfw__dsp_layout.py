#!/usr/bin/env python3
"""Map where the CS40L25 download blocks actually land in DSP memory.

The 137 core blocks are described in the project notes only as "identical to the
Cirrus 0A0603 reference". That says nothing about *what* they configure, so this
groups them by DSP address window to show the spatial layout: which parts of the
chip's memory the firmware populates, how densely, and where the three Surface
appended regions sit relative to them.

Windows are the ones the notes name for VIBEGEN (XM 0x02800000, YM 0x03400000);
the PM/ROM/other blocks are grouped by their own top byte so the report does not
impose a naming the evidence does not support.
"""
from __future__ import annotations

import hashlib
import json
import struct
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
HAP = HERE / "out" / "SurfaceTouchpadHaptic_2.9.139"

# Windows named in the project notes.
NAMED = {
    (0x02800000, 0x02C00000): "XM / algorithm + control (VIBEGEN base)",
    (0x02B80000, 0x02BC0000): "ASM / AMP registers (init table group)",
    (0x02BC0000, 0x02C00000): "DSP control (incl. 0x02BC1000 enable)",
    (0x03400000, 0x03800000): "YM / wavetable (VIBEGEN WAVETABLEYM base)",
}


def window_for(addr: int) -> str:
    for (lo, hi), name in NAMED.items():
        if lo <= addr < hi:
            return name
    top = addr >> 24
    return f"other 0x{top:02X}xxxxxx"


def main():
    blocks = json.load(open(HAP / "haptic_blocks_0.json", encoding="utf-8"))
    body = (HAP / "body_0.bin").read_bytes()
    pos, payload = 8, {}
    for b in blocks:
        payload[b["sequence"]] = body[pos + 14:pos + 14 + b["length"]]
        pos += 14 + b["length"]

    groups = defaultdict(lambda: dict(blocks=0, payload_bytes=0, min=None, max=None,
                                      sequences=[]))
    for b in blocks:
        w = window_for(b["address"])
        g = groups[w]
        g["blocks"] += 1
        g["payload_bytes"] += b["length"]
        g["sequences"].append(b["sequence"])
        lo, hi = b["address"], b["address"] + b["length"]
        g["min"] = lo if g["min"] is None else min(g["min"], lo)
        g["max"] = hi if g["max"] is None else max(g["max"], hi)

    core = [b for b in blocks if b["sequence"] < 137]
    added = [b for b in blocks if b["sequence"] >= 137]
    total_payload = sum(b["length"] for b in blocks)

    print(f"blocks total {len(blocks)}  payload {total_payload:,} B")
    print(f"  core 0-136   {len(core)} blocks  {sum(b['length'] for b in core):,} B")
    print(f"  appended 137+ {len(added)} blocks {sum(b['length'] for b in added):,} B")
    print()
    print("by DSP memory window:")
    for name, g in sorted(groups.items(), key=lambda kv: -kv[1]["payload_bytes"]):
        span = g["max"] - g["min"]
        density = g["payload_bytes"] / span if span else 0
        print(f"  {name}")
        print(f"      blocks {g['blocks']:>3}  payload {g['payload_bytes']:>6,} B  "
              f"span 0x{g['min']:08X}..0x{g['max']:08X} ({span:,} B)  "
              f"density {density:.1%}")

    # The three appended regions, for direct comparison against the core layout.
    # XM wavetable ends where WSEQ begins; the advertised XM capacity (2480)
    # applies to the wavetable alone, not to wavetable+WSEQ together.
    print()
    print("Surface-appended regions (the only haptic data not in the Cirrus core):")
    app_regions = (("XM wavetable", 0x02800B60, 0x028014C8, 2480),
                   ("YM wavetable", 0x03400000, 0x03400FD0, 7000),
                   ("WSEQ", 0x028016D0, 0x02801894, None))
    for label, lo, hi, capacity in app_regions:
        sel = [b for b in added if lo <= b["address"] < hi]
        used = sum(b["length"] for b in sel)
        inside = [b for b in core if lo <= b["address"] < hi]
        pct = f" ({used / capacity:.1%} of advertised)" if capacity else ""
        print(f"  {label:<14} 0x{lo:08X}..0x{hi:08X}  {used:>5} B in {len(sel)} blocks"
              f"{pct}  overlapping core blocks: {len(inside)}")

    # Contiguity: a fully covered span means the region is one dense structure
    # rather than a set of independent registers.
    print()
    print("contiguity of the dense windows:")
    for lo, hi, label in ((0x03800000, 0x03804DE4, "0x03800000 table"),
                          (0x03400000, 0x03400FD0, "YM wavetable")):
        sel = [b for b in blocks if lo <= b["address"] < hi]
        span = hi - lo
        used = sum(b["length"] for b in sel)
        gaps = span - used
        print(f"  {label:<20} span {span:,} B  written {used:,} B  gaps {gaps} B  "
              f"blocks {len(sel)}")

    # Sparse windows: how many distinct pages, i.e. how scattered the writes are.
    print()
    sparse = [b for b in core if (b["address"] >> 24) == 0x02]
    pages = sorted({b["address"] >> 16 for b in sparse})
    print(f"  0x02xxxxxx: {len(sparse)} blocks across {len(pages)} 64-KB pages "
          f"{[hex(p << 16) for p in pages]}")
    print(f"    -> point writes into a large address space, not a dense region")

    # Sequence order: blocks are written in ascending address order, which is
    # what a download loop would do and makes the table reproducible.
    addrs = [b["address"] for b in blocks]
    print(f"\n  sequence order == ascending address order: {addrs == sorted(addrs)}")

    out = dict(
        blocks_total=len(blocks), payload_bytes=total_payload,
        core=dict(count=len(core), payload=sum(b["length"] for b in core)),
        appended=dict(count=len(added), payload=sum(b["length"] for b in added)),
        windows={name: dict(blocks=g["blocks"], payload_bytes=g["payload_bytes"],
                            min=f"0x{g['min']:08X}", max=f"0x{g['max']:08X}",
                            span=g["max"] - g["min"],
                            density=round(g["payload_bytes"] / (g["max"] - g["min"]), 4)
                            if g["max"] > g["min"] else None,
                            first_seq=min(g["sequences"]), last_seq=max(g["sequences"]))
              for name, g in groups.items()},
        dense_windows=[
            dict(label="0x03800000 table", base="0x03800000", span=hi1 - lo1,
                 written=sum(b["length"] for b in blocks if lo1 <= b["address"] < hi1),
                 blocks=len([b for b in blocks if lo1 <= b["address"] < hi1]))
            for lo1, hi1 in ((0x03800000, 0x03804DE4),)
        ],
        sparse_windows=[
            dict(label="0x02xxxxxx", blocks=len(sparse),
                 pages=[f"0x{p << 16:08X}" for p in pages])
        ],
        appended_regions=[
            dict(label=label, base=f"0x{lo:08X}", end=f"0x{hi:08X}",
                 written=sum(b["length"] for b in added if lo <= b["address"] < hi),
                 blocks=len([b for b in added if lo <= b["address"] < hi]),
                 advertised_capacity=capacity,
                 utilisation=round(sum(b["length"] for b in added
                                       if lo <= b["address"] < hi) / capacity, 4)
                 if capacity else None)
            for label, lo, hi, capacity in app_regions
        ],
        sequence_is_address_ordered=addrs == sorted(addrs),
    )
    (HAP / "dsp_layout.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
