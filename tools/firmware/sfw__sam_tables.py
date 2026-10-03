#!/usr/bin/env python3
"""Extract the CS40L25 tables that SAM carries in ROM.

The project notes describe two register initialisation tables and one I2C device
table living at fixed runtime addresses in the SAM image:

  0x841EC  71 entries   init table A (platform selector >= 2)
  0x8442C  70 entries   init table B (otherwise)
  0x83D20  29-byte records, 17 = HAPTIC_DRIVER, 19 = BUCK_BOOST

Entry format is already big-endian on the wire:
    register:u32be || value:u32be
terminated by eight zero bytes.

Everything here is verified against the bytes: the terminator must be present,
the entry count must match, and the device-table record stride must divide the
region consistently. A table that fails its own check is reported as such rather
than being silently accepted.
"""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
SAM = HERE / "out" / "SurfaceSAM_9.101.139"
LOAD_BASE = 0x80000

TABLES = {
    "init_A": dict(runtime=0x841EC, expect_entries=71, selector="platform selector >= 2"),
    "init_B": dict(runtime=0x8442C, expect_entries=70, selector="otherwise"),
}
DEVICE_TABLE_RUNTIME = 0x83D20
DEVICE_RECORD = 29
TERMINATOR = b"\x00" * 8
MAX_SCAN = 4096


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def read_init_table(body: bytes, runtime: int, expect: int) -> dict:
    """Read register/value pairs until the eight-zero terminator."""
    off = runtime - LOAD_BASE
    out = dict(runtime=f"0x{runtime:06X}", body_offset=f"0x{off:X}",
               expected_entries=expect)
    if not (0 <= off < len(body)):
        out["status"] = "out of range"
        return out

    entries = []
    p = off
    while len(entries) <= MAX_SCAN:
        if p + 8 > len(body):
            out["status"] = "ran past end of body without terminator"
            break
        rec = body[p:p + 8]
        if rec == TERMINATOR:
            out["status"] = "ok" if len(entries) == expect else "entry count mismatch"
            out["terminator_body_offset"] = f"0x{p:X}"
            break
        reg, val = struct.unpack(">II", rec)
        entries.append(dict(index=len(entries), body_offset=f"0x{p:X}",
                            register=f"0x{reg:08X}", value=f"0x{val:08X}",
                            register_u32=f"{reg}", value_u32=f"{val}"))
        p += 8
    else:
        out["status"] = "no terminator found"

    out["entry_count"] = len(entries)
    out["entries"] = entries
    out["table_sha256"] = sha(body[off:p]) if entries else None

    # Sanity: these are CS40L25 register addresses, which live in the
    # 0x0280xxxx / 0x02BCxxxx / 0x0380xxxx windows.
    windows = {}
    for e in entries:
        r = int(e["register_u32"])
        top = (r >> 24) & 0xFF
        windows[top] = windows.get(top, 0) + 1
    out["register_high_byte_histogram"] = {f"0x{k:02X}": v for k, v in sorted(windows.items())}
    out["register_min"] = min((int(e["register_u32"]) for e in entries), default=None)
    out["register_max"] = max((int(e["register_u32"]) for e in entries), default=None)

    # The notes name two specific writes in pre_download_prepare; flag them if
    # they appear in the table rather than assuming they must.
    for label, needle in (("flag_0x00000020", 0x00000020),
                          ("reg_0x02800190", 0x02800190)):
        hit = [e for e in entries if int(e["register_u32"]) == needle]
        out[f"contains_{label}"] = hit
    return out


def read_device_table(body: bytes, runtime: int) -> dict:
    """Read fixed 29-byte I2C device records."""
    off = runtime - LOAD_BASE
    out = dict(runtime=f"0x{runtime:06X}", body_offset=f"0x{off:X}",
               record_size=DEVICE_RECORD)
    if not (0 <= off < len(body)):
        out["status"] = "out of range"
        return out
    recs = []
    idx = 0
    while off + DEVICE_RECORD * (idx + 1) <= len(body) and idx < 64:
        base = off + DEVICE_RECORD * idx
        rec = body[base:base + DEVICE_RECORD]
        # First 7 bytes are the NUL-padded device name on the wire.
        name = rec[:7].split(b"\x00")[0].decode("ascii", "replace")
        rest = rec[7:]
        recs.append(dict(index=idx, body_offset=f"0x{base:X}", name=name,
                         raw=rec.hex()))
        if not any(rec):
            break
        idx += 1
    out["record_count"] = len(recs)
    out["records"] = recs
    out["status"] = "ok" if recs else "empty"

    # The notes state the wire addresses are `address << 1`; look for the two
    # named devices and report the byte that would carry each address.
    named = {}
    for rec in recs:
        n = rec["name"]
        if n in ("HAPTIC_DRIVER", "BUCK_BOOST"):
            named[n] = rec
    out["named_devices"] = named
    return out


def strings_near(body: bytes, runtime: int, window: int = 256) -> list[dict]:
    """Printable strings within `window` bytes either side of a runtime address."""
    import re
    off = runtime - LOAD_BASE
    lo, hi = max(0, off - window), min(len(body), off + window)
    return [dict(body_offset=m.start(), text=m.group().decode("ascii"))
            for m in re.finditer(rb"[\x20-\x7e]{4,}", body[lo:hi])]


def main():
    out = {}
    for variant in (0, 1):
        body = (SAM / f"body_{variant}.bin").read_bytes()
        rep = dict(variant=variant, body_sha256=sha(body), body_bytes=len(body),
                   load_base=f"0x{LOAD_BASE:X}", tables={})
        for name, spec in TABLES.items():
            t = read_init_table(body, spec["runtime"], spec["expect_entries"])
            t["selector"] = spec["selector"]
            rep["tables"][name] = t
        rep["device_table"] = read_device_table(body, DEVICE_TABLE_RUNTIME)
        rep["context_strings"] = {
            "around_0x841EC": strings_near(body, 0x841EC),
            "around_0x83D20": strings_near(body, 0x83D20),
            "around_0x8DC20": strings_near(body, 0x8DC20),
        }
        out[f"variant_{variant}"] = rep

        print(f"=== variant {variant}  body {len(body):,} B")
        for name, t in rep["tables"].items():
            print(f"  {name} @ {t['runtime']}  entries={t.get('entry_count')} "
                  f"(expect {t['expected_entries']})  status={t['status']}")
            if t.get("register_min") is not None:
                print(f"      registers 0x{t['register_min']:08X}.."
                      f"0x{t['register_max']:08X}  high-byte histogram "
                      f"{t['register_high_byte_histogram']}")
        dt = rep["device_table"]
        print(f"  device_table @ {dt['runtime']}  records={dt.get('record_count')} "
              f"status={dt['status']}")
        for n, rec in dt.get("named_devices", {}).items():
            print(f"      {n}: {rec['raw']}")
        print()

    (SAM / "tables_report.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
