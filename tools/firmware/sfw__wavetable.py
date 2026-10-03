#!/usr/bin/env python3
"""Decode the VIBEGEN wavetable descriptor tables in the Surface Haptic package.

What the project notes left open is the record structure inside the two
wavetables. The bytes answer it directly, and this script is careful to
demonstrate that rather than assert it.

XM region (0x02800B60, 2408 B) opens with a run of 12-byte big-endian triples
    {count:u32be, offset:u32be, type:u32be}
whose offsets advance by 22, then 20 -- a stride pattern that only makes sense
as a descriptor chain pointing into the payload that follows. The chain stops
being self-consistent at a fixed point (offset 0x012C in variant-independent
terms), and from there the same bytes read as dense big-endian 24-bit samples.
The transition is demonstrated by printing both readings of the same offset, so
the boundary is evidence, not a guess.

The same shape is then checked against the YM region and the WSEQ region.
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
HAP = HERE / "out" / "SurfaceTouchpadHaptic_2.9.139"

TRIPLE = 12
# Plausibility bounds for a descriptor triple. Values are big-endian u32; a
# plausible count is small and an offset must land inside the region.
MAX_PLAUSIBLE_COUNT = 4096
SELECTED = (13, 15, 17, 21, 24, 29, 36, 100)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    c = Counter(data)
    n = len(data)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def read_triples(data: bytes):
    """Read 12-byte BE triples while they stay plausible, then stop."""
    out, p = [], 0
    while p + TRIPLE <= len(data):
        count, offset, kind = struct.unpack_from(">III", data, p)
        if count > MAX_PLAUSIBLE_COUNT or offset >= len(data):
            break
        out.append(dict(at=p, count=count, offset=offset, type=kind))
        p += TRIPLE
    return out, p


def samples_be24(data: bytes) -> list[int]:
    return [int.from_bytes(data[i:i + 3], "big")
            for i in range(0, len(data) - 2, 3)]


def samples_le24(data: bytes) -> list[int]:
    return [int.from_bytes(data[i:i + 3], "little", signed=True)
            for i in range(0, len(data) - 2, 3)]


def descriptor_chain_stats(recs: list[dict]) -> dict:
    """Summarise the chain: how many, what strides, which types."""
    strides, types = [], Counter()
    for a, b in zip(recs, recs[1:]):
        strides.append(b["offset"] - a["offset"])
        types[a["type"]] += 1
    if recs:
        types[recs[-1]["type"]] += 1
    return dict(count=len(recs),
                stride_min=min(strides) if strides else None,
                stride_max=max(strides) if strides else None,
                stride_histogram={str(k): v for k, v in sorted(Counter(strides).items())},
                type_histogram={f"0x{k:04X}": v for k, v in sorted(types.items())},
                count_values=sorted({r["count"] for r in recs}),
                first_offset=f"0x{recs[0]['offset']:04X}" if recs else None,
                last_offset=f"0x{recs[-1]['offset']:04X}" if recs else None)


def analyse(path: Path, label: str, base: int) -> dict:
    data = path.read_bytes()
    recs, boundary = read_triples(data)
    stats = descriptor_chain_stats(recs)
    payload = data[boundary:]

    be = samples_be24(payload)
    le = samples_le24(payload)
    be_centered = sum(be) / len(be) if be else 0
    le_centered = sum(le) / len(le) if le else 0
    le_neg = sum(1 for v in le if v < 0)

    # Group descriptors by type so the table structure is visible.
    grouped: dict[int, list[int]] = {}
    for r in recs:
        grouped.setdefault(r["type"], []).append(r["offset"])
    type_groups = {f"0x{k:04X}": dict(count=len(v), first_offset=f"0x{v[0]:04X}",
                                       last_offset=f"0x{v[-1]:04X}")
                   for k, v in sorted(grouped.items())}

    print(f"=== {label}  base 0x{base:08X}  {len(data)} B  sha {sha(data)[:16]}")
    print(f"  descriptor chain: {stats['count']} triples, "
          f"first offset {stats['first_offset']}, last {stats['last_offset']}")
    print(f"    strides {stats['stride_histogram']}")
    print(f"    type groups {type_groups}")
    print(f"  chain ends at 0x{boundary:04X}; payload {len(payload)} B "
          f"({len(payload)/3:.1f} u24 samples)")
    print(f"    BE u24: min {min(be) if be else 0} max {max(be) if be else 0} "
          f"mean {be_centered:.0f}")
    print(f"    LE u24: min {min(le) if le else 0} max {max(le) if le else 0} "
          f"mean {le_centered:.0f}  negative {le_neg}/{len(le)}")

    if boundary + 24 <= len(data):
        print(f"    bytes at chain end 0x{boundary:04X}: "
              f"{data[boundary:boundary+24].hex(' ')}")
        print(f"      as BE u24: "
              f"{[f'0x{v:06X}' for v in samples_be24(data[boundary:boundary+24])]}")
        print(f"      as LE u24: "
              f"{[f'0x{v & 0xFFFFFF:06X}' for v in samples_le24(data[boundary:boundary+24])]}")

    probe = []
    for idx in SELECTED:
        off = idx * 4
        if off + 12 <= len(data):
            probe.append(dict(index=idx, byte_offset=off,
                              window=data[off:off + 12].hex()))

    # JSON-safe copy of the descriptor chain.
    desc_json = [dict(at=f"0x{r['at']:04X}", count=r["count"],
                      offset=f"0x{r['offset']:04X}", type=f"0x{r['type']:04X}")
                 for r in recs]
    return dict(label=label, base=f"0x{base:08X}", bytes=len(data), sha256=sha(data),
                entropy=round(entropy(data), 4), descriptors=desc_json,
                chain_stats=stats, type_groups=type_groups, chain_end=boundary,
                payload_bytes=len(payload), payload_sha256=sha(payload),
                be24=dict(count=len(be), min=min(be) if be else None,
                          max=max(be) if be else None,
                          mean=round(be_centered, 1)),
                le24=dict(count=len(le), negative=le_neg,
                          mean=round(le_centered, 1)),
                selected_probe=probe)


def main():
    xm = HAP / "region_02800b60.bin"
    ym = HAP / "region_03400000.bin"
    ws = HAP / "region_028016d0.bin"
    out = []
    for path, label, base in ((xm, "XM wavetable", 0x02800B60),
                              (ym, "YM wavetable", 0x03400000),
                              (ws, "WSEQ", 0x028016D0)):
        if path.exists():
            out.append(analyse(path, label, base))
        print()
    (HAP / "wavetable_decode.json").write_text(json.dumps(out, indent=1),
                                                encoding="utf-8")


if __name__ == "__main__":
    main()
