#!/usr/bin/env python3
"""Recover the SAM startup RAM images and re-derive the touchpad/haptic tables.

The SAM bodies do not contain the built-in CS40L25 download descriptors, the
touchpad state table or the HID descriptor. They are *decompressed into RAM at
boot* by a small LZSS-style codec. The dispatcher table that locates the two
compressed segments was recovered per variant (0xE755C / 0xE915C).

Codec, transcribed from the startup decompressor:

    token       = byte()
    literals    = token & 3        ; 0 means "read another byte, then +3"
    matches     = token >> 4       ; 15 means "read another byte, then +15"
    literals   -= 1
    copy `literals` bytes verbatim
    if matches:
        low       = byte()
        high      = (token >> 2) & 3 ; 3 means "read another byte"
        distance  = low + (high << 8)
        copy `matches + 2` bytes from output[-distance]   # may overlap: byte-wise

Every bound is checked, and the decoded segment destinations must be exactly
0x11DDB0 and 0x1BB8, which is what makes the decode trustworthy.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
SAM = HERE / "out" / "SurfaceSAM_9.101.139"
BASE = 0x80000
DECOMPRESSOR = 0x200000

# Dispatcher table address per variant, and the RAM layout it must produce.
TABLES = {0: 0xE755C, 1: 0xE915C}
EXPECTED_DESTS = [0x11DDB0, 0x1BB8]

# Named functions the project notes recovered, for cross-reference.
KNOWN_FUNCTIONS = {
    0x9527E: ("startup_decompressor", 0x952FA),
    0xDC5BE: ("set_boost_parameter_indirect", 0xDC5EE),
    0xE455A: ("boost_set_parameter", 0xE4606),
}


def require(cond, msg):
    if not cond:
        raise ValueError(msg)


def grab(data: bytes, offset: int, size: int) -> bytes:
    require(0 <= offset <= len(data) and 0 <= size <= len(data) - offset,
            f"out-of-bounds grab at {offset:#x} size {size:#x}")
    return bytes(data[offset:offset + size])


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def decompress(encoded: bytes, limit: int = DECOMPRESSOR) -> bytes:
    """Bounded transcription of the startup codec, including overlapping backrefs."""
    cursor = 0
    out = bytearray()

    def byte() -> int:
        nonlocal cursor
        require(cursor < len(encoded), "truncated compressed token")
        v = encoded[cursor]
        cursor += 1
        return v

    while cursor < len(encoded):
        token = byte()
        literals = token & 3
        if literals == 0:
            literals = byte() + 3
        matches = token >> 4
        if matches == 15:
            matches = byte() + 15
        literals -= 1
        require(len(out) + literals <= limit, "decompression output limit")
        out.extend(grab(encoded, cursor, literals))
        cursor += literals
        if matches:
            low = byte()
            high = (token >> 2) & 3
            if high == 3:
                high = byte()
            distance = low + (high << 8)
            require(0 < distance <= len(out), "invalid compressed back-reference")
            require(len(out) + matches + 2 <= limit, "decompression output limit")
            for _ in range(matches + 2):
                out.append(out[-distance])
    return bytes(out)


def decode_startup(body: bytes, variant: int) -> dict:
    table = TABLES[variant]
    off = table - BASE
    require(0 <= off < len(body), f"variant {variant}: table 0x{table:X} outside body")

    zero_fn = (table + u32(body, off)) & 0xFFFFFFFF
    zero = []
    cursor = off + 4
    while (size := u32(body, cursor)) != 0:
        require(len(zero) < 16, "unterminated zero table")
        zero.append(dict(size=size, address=u32(body, cursor + 4)))
        cursor += 8
    cursor += 4

    segments = []
    for _ in range(2):
        fn = (BASE + cursor + u32(body, cursor)) & 0xFFFFFFFF
        header = cursor + 4
        source = header + u32(body, header)
        encoded_size = u32(body, header + 4)
        require(encoded_size & 1 == 0, "unsupported R9-relative destination")
        destination = u32(body, header + 8)
        encoded = grab(body, source, encoded_size >> 1)
        decoded = decompress(encoded)
        segments.append(dict(table_record=f"0x{BASE + cursor:08X}", decoder=f"0x{fn & ~1:08X}",
                             source=f"0x{BASE + source:08X}", destination=f"0x{destination:08X}",
                             encoded_bytes=len(encoded), decoded_bytes=len(decoded),
                             decoded_sha256=hashlib.sha256(decoded).hexdigest(),
                             decoded=decoded))
        cursor = header + 12

    require([int(s["destination"], 16) for s in segments] == EXPECTED_DESTS,
            f"variant {variant}: RAM layout mismatch "
            f"{[s['destination'] for s in segments]} != {[hex(d) for d in EXPECTED_DESTS]}")
    for a in segments:
        alo, ahi = int(a["destination"], 16), int(a["destination"], 16) + a["decoded_bytes"]
        for z in zero:
            require(ahi <= z["address"] or alo >= z["address"] + z["size"],
                    "RAM segment overlaps a zeroed region")
    return dict(table_address=f"0x{table:08X}", table_end=f"0x{BASE + cursor:08X}",
                zero_function=f"0x{zero_fn & ~1:08X}", zero_ranges=zero,
                segments=segments)


def read_ram(ram: bytes, addr: int, size: int) -> bytes:
    """Read from the segment that starts at 0x11DDB0."""
    return grab(ram, addr - 0x11DDB0, size)


def state_table(ram: bytes, table_addr: int) -> list[dict]:
    """14-byte records: sid:u16, name_ptr:u32, fn:u32, child_ptr:u32."""
    out = []
    for n in range(64):
        try:
            raw = read_ram(ram, table_addr + n * 14, 14)
        except ValueError:
            break
        if raw == b"\x00" * 14:
            break
        sid, name, fn, child = struct.unpack("<HIII", raw)
        if name == 0 and fn == 0:
            break
        out.append(dict(index=n, sid=sid, name_ptr=f"0x{name:08X}",
                        fn=f"0x{fn:08X}", child_ptr=f"0x{child:08X}"))
    return out


def cstring(ram: bytes, addr: int, limit: int = 64) -> str:
    off = addr - 0x11DDB0
    if not (0 <= off < len(ram)):
        return ""
    end = ram.find(b"\x00", off, off + limit)
    if end < 0:
        return ""
    try:
        return ram[off:end].decode("ascii")
    except UnicodeDecodeError:
        return ""


def touchpad_hid(ram: bytes) -> tuple[list[dict], bytes | None]:
    """Find the touchpad HID descriptor embedded in RAM."""
    out = []
    for m in re.finditer(rb"Touchpad", ram):
        out.append(dict(ram_offset=m.start(), ram_address=f"0x{0x11DDB0 + m.start():08X}"))
    return out, None


def main():
    report = {}
    for variant in (0, 1):
        body = (SAM / f"body_{variant}.bin").read_bytes()
        st = decode_startup(body, variant)
        print(f"=== variant {variant}")
        print(f"  dispatcher table {st['table_address']}  zero fn {st['zero_function']}")
        print(f"  zero ranges: {[(f'0x{z['address']:08X}', z['size']) for z in st['zero_ranges']]}")
        for s in st["segments"]:
            print(f"  segment dest {s['destination']}  encoded {s['encoded_bytes']:,} -> "
                  f"decoded {s['decoded_bytes']:,}  sha {s['decoded_sha256'][:16]}")
            (SAM / f"ram_{s['destination'][2:]}.bin").write_bytes(s["decoded"])
        seg0 = st["segments"][0]["decoded"]

        # The notes name these two 14-byte state tables in variant 0 RAM.
        tables = {}
        for label, addr in (("touchpad_state_0x11E5E4", 0x11E5E4),
                            ("second_state_0x123444", 0x123444)):
            recs = state_table(seg0, addr)
            for r in recs:
                r["name"] = cstring(seg0, int(r["name_ptr"], 16))
            tables[label] = recs
            print(f"  {label}: {len(recs)} records")
            for r in recs[:8]:
                print(f"      [{r['index']}] sid={r['sid']} fn={r['fn']} name={r['name']!r}")

        # 5-word vtable and the 8 bytes right after it, per the notes.
        try:
            vtable = struct.unpack("<5I", read_ram(seg0, 0x11E900, 20))
            initial = read_ram(seg0, 0x11E920, 8).hex()
            print(f"  boost vtable @0x11E900: {[f'0x{x:08X}' for x in vtable]}")
            print(f"  boost initial bytes @0x11E920: {initial}")
            tables["boost_vtable"] = [f"0x{x:08X}" for x in vtable]
            tables["boost_initial_bytes"] = initial
        except ValueError as exc:
            print(f"  boost vtable unavailable: {exc}")

        tp, _ = touchpad_hid(seg0)
        print(f"  'Touchpad' occurrences in RAM: {len(tp)}")
        if tp:
            print(f"      first at {tp[0]['ram_address']}")

        report[f"variant_{variant}"] = dict(
            body_sha256=hashlib.sha256(body).hexdigest(),
            table_address=st["table_address"], table_end=st["table_end"],
            zero_function=st["zero_function"], zero_ranges=st["zero_ranges"],
            segments=[{k: v for k, v in s.items() if k != "decoded"}
                      for s in st["segments"]],
            tables=tables, touchpad_strings=tp)
        print()

    (SAM / "startup_ram_report.json").write_text(json.dumps(report, indent=1),
                                                 encoding="utf-8")


if __name__ == "__main__":
    main()
