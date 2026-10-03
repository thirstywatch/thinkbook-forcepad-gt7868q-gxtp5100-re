#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only audit of the decrypted GT7868Q payload-A data.

This deliberately does not touch a device.  It checks the claims that matter
for the haptic path: whether the payload contains an 8051 vector table, ARM
code-like I2C host constants, or a convincing AW86927 identity.

The payload is the Goodix firmware_info data area.  Each byte is unwhitened
with the already established 1024-byte table and phase (container-relative
316).  The result is diagnostic evidence only; it is not a firmware flasher.
"""

from __future__ import annotations

import argparse
import math
import os
import struct
from collections import Counter


PHASE = 316
DATA_OFF = 0x100
MAX_SUBSYS = 28


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def find_container(data: bytes) -> int:
    for off in range(0, min(len(data) - DATA_OFF, 0x10000)):
        size = int.from_bytes(data[off:off + 4], "big")
        if not 1000 < size <= len(data) - off:
            continue
        checksum = int.from_bytes(data[off + 4:off + 6], "big")
        body = data[off + 6:off + 6 + size]
        if sum(body) & 0xFFFF == checksum:
            return off
    raise ValueError("no official Goodix container found")


def parse(data: bytes, container: int) -> list[tuple[int, int, int]]:
    entries = []
    for idx in range(MAX_SUBSYS):
        row = container + 0x20 + idx * 8
        kind = data[row]
        size = int.from_bytes(data[row + 1:row + 5], "big")
        flash = int.from_bytes(data[row + 5:row + 7], "big") << 8
        if kind == 0 and size == 0:
            break
        entries.append((kind, size, flash))
    return entries


def decrypt_blocks(data: bytes, container: int, key: bytes):
    entries = parse(data, container)
    cursor = container + DATA_OFF
    for idx, (kind, size, flash) in enumerate(entries):
        raw = data[cursor:cursor + size]
        if len(raw) != size:
            raise ValueError(f"subsys {idx} is truncated")
        # PHASE is container-relative; `relative` starts at the data area.
        plain = bytes(
            value ^ key[(relative + DATA_OFF + PHASE) % len(key)]
            for relative, value in enumerate(raw)
        )
        yield idx, kind, size, flash, plain
        cursor += size


def vector_score(block: bytes) -> tuple[int, list[int]]:
    """Score the mandatory 8051 reset/interrupt vector positions."""
    offsets = (0x00, 0x03, 0x0B, 0x13, 0x1B, 0x23)
    present = [off for off in offsets if off < len(block) and block[off] in (0x02, 0x12)]
    return len(present), present


def count_patterns(block: bytes) -> dict[str, int]:
    patterns = {
        "0x5A": b"\x5a",
        "AW86927_BE": b"\x92\x70",
        "AW86927_LE": b"\x70\x92",
        "I2C_START_le32": struct.pack("<I", 0x100),
        "I2C_STOP_le32": struct.pack("<I", 0x200),
        "I2C_ACK_le32": struct.pack("<I", 0x400),
        "I2C_SWRST_le32": struct.pack("<I", 0x8000),
        "I2C1_BASE_le32": struct.pack("<I", 0x40005400),
        "I2C2_BASE_le32": struct.pack("<I", 0x40005800),
    }
    return {name: block.count(pattern) for name, pattern in patterns.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("firmware", help="Goodix firmware/container file")
    parser.add_argument("key", help="1024-byte whitening table")
    args = parser.parse_args()

    data = open(args.firmware, "rb").read()
    key = open(args.key, "rb").read()
    if len(key) != 1024:
        raise SystemExit("key must be exactly 1024 bytes")

    container = find_container(data)
    blocks = list(decrypt_blocks(data, container, key))
    print(f"firmware={os.path.basename(args.firmware)}")
    print(f"container=0x{container:X} blocks={len(blocks)}")
    print("idx type flash size H0 vector_score vector_offsets "
          "0x5A AW86927_BE AW86927_LE I2C_START I2C_STOP I2C_ACK "
          "I2C_SWRST I2C1_BASE I2C2_BASE")

    totals = Counter()
    for idx, kind, size, flash, plain in blocks:
        score, offsets = vector_score(plain)
        patterns = count_patterns(plain)
        totals.update(patterns)
        print(
            f"{idx:>3} 0x{kind:02X} 0x{flash:05X} 0x{size:05X} "
            f"{entropy(plain):.4f} {score}/6 {','.join(f'{x:X}' for x in offsets) or '-'} "
            + " ".join(str(patterns[name]) for name in (
                "0x5A", "AW86927_BE", "AW86927_LE", "I2C_START_le32",
                "I2C_STOP_le32", "I2C_ACK_le32", "I2C_SWRST_le32",
                "I2C1_BASE_le32", "I2C2_BASE_le32"))
        )

    print(f"TOTAL 0x5A={totals['0x5A']} AW86927_BE={totals['AW86927_BE']} "
          f"AW86927_LE={totals['AW86927_LE']} I2C_START={totals['I2C_START_le32']} "
          f"I2C_STOP={totals['I2C_STOP_le32']} I2C_ACK={totals['I2C_ACK_le32']} "
          f"I2C_SWRST={totals['I2C_SWRST_le32']} "
          f"I2C1_BASE={totals['I2C1_BASE_le32']} I2C2_BASE={totals['I2C2_BASE_le32']}")
    print("NOTE: this is a negative offline result, not proof that the live GT7868Q "
          "cannot drive AW86927; the payload contains data/ISP, not the runtime code.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
