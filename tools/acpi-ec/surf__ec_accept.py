#!/usr/bin/env python3
"""ec_accept.py - EC firmware "shape fingerprint" acceptor.

Purpose
-------
The Surface SAM (Surface Aggregator, i.e. the Surface EC) firmware is PLAINTEXT:
Thumb code + a large string pool + big-endian reg:value tables.  The Lenovo EC
firmware (NJME01WW.exe / NJME07WW.exe) is ENCRYPTED + LZMA, still unsolved.

This tool turns "the SAM we already have" into a measurable TEMPLATE, so that a
candidate decryption of the Lenovo payload can be scored automatically instead
of being eyeballed.  Calibrate it on SAM first (must score high), then feed it
every candidate transform of the Lenovo overlay.

Metrics (all computed on a raw body byte string)
------------------------------------------------
  H0            Shannon entropy, bits/byte
  zero%         fraction of 0x00
  print%        fraction in 0x20..0x7E
  str/KB        runs >= 6 printable chars, per KiB
  kw            EC / haptic identifier hits (TOUCHPAD, HAPTIC, BUCK, BOOST ...)
  be_tab        big-endian u32 reg:u32 val tables terminated by 8 zero bytes
  wide%         fraction of halfwords whose top 5 bits are 11101/11110/11111
                (Thumb-2 32-bit instruction prefix)

Usage
-----
  python ec_accept.py --capsule SurfaceSAM_9.101.139.bin
  python ec_accept.py --overlay NJME01WW.exe
  python ec_accept.py --body somebody.bin
"""

from __future__ import annotations

import argparse
import math
import re
import struct
import sys
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------- unpack

def parse_cfu_stream(buf: bytes, start: int):
    """Reassemble one CFU image starting at `start`.

    Returns (image, end_offset) or (None, None) if the stream is not tidy.
    Record = u32 LE component_offset || u8 length || data[length]
    Require component_offset == len(so_far) for every record (no holes).
    """
    out = bytearray()
    i = start
    n = len(buf)
    while i + 5 <= n:
        off = int.from_bytes(buf[i:i + 4], "little")
        ln = buf[i + 4]
        if ln == 0 or i + 5 + ln > n:
            break
        if off != len(out):
            break
        out += buf[i + 5:i + 5 + ln]
        i += 5 + ln
        if len(out) >= 0x200000:      # sanity cap
            break
    if len(out) < 64:
        return None, None
    return bytes(out), i


def parse_component(comp: bytes):
    if len(comp) < 20:
        return None
    hs, o1, o2, ext, body = struct.unpack_from("<IIIII", comp, 0)
    if hs != 20 or o1 != 1 or o2 != 1:
        return None
    if not (20 <= ext < body < len(comp)):
        return None
    return dict(header_size=hs, extension_offset=ext, body_offset=body)


def unpack_capsule(data: bytes):
    """Find FMP/CFU offers and reassemble every Component image."""
    cands = []
    for i in range(0, len(data) - 16):
        if data[i + 3] == 0xB0 and data[i + 14] == 0x3C and data[i + 15] == 0x00:
            cands.append(i)
    results = []
    seen = set()
    for pos in cands:
        # a real offer is followed by a tidy CFU stream
        for skip in (16,):
            start = pos + skip
            if start in seen:
                continue
            img, _ = parse_cfu_stream(data, start)
            if not img:
                continue
            cinfo = parse_component(img)
            if not cinfo:
                continue
            seen.add(start)
            results.append(dict(offer=data[pos:pos + 16],
                                image=img,
                                body=img[cinfo["body_offset"]:],
                                **cinfo))
    return results


def extract_overlay(path: Path):
    """Delphi PE: everything after the last section = overlay."""
    data = path.read_bytes()
    if data[:2] != b"MZ":
        return None, "not MZ"
    pe = int.from_bytes(data[0x3C:0x40], "little")
    if data[pe:pe + 4] != b"PE\0\0":
        return None, "no PE at 0x3C"
    nsec = int.from_bytes(data[pe + 6:pe + 8], "little")
    optsz = int.from_bytes(data[pe + 20:pe + 22], "little")
    sec = pe + 24 + optsz
    end = 0
    for k in range(nsec):
        e = sec + k * 40
        raws = int.from_bytes(data[e + 16:e + 20], "little")
        rawp = int.from_bytes(data[e + 20:e + 24], "little")
        end = max(end, rawp + raws)
    return data[end:], f"overlay @0x{end:X} ({len(data) - end:,} B)"


# ---------------------------------------------------------------- metrics

KEYWORDS = [
    b"TOUCHPAD", b"TouchpadTask", b"ActuateHaptic", b"HAPTIC", b"Haptic",
    b"BUCK", b"BuckBoost", b"BOOST", b"FORCE_SENSOR", b"TP_TEMPERATURE",
    b"LRA", b"VIBRA", b"VIBEGEN", b"TRIG", b"AW86927", b"86927",
    b"EC0", b"EC_", b"ECFW", b"I2C", b"SPI", b"GPIO", b"FWUPDATE",
    b"TRACKPAD", b"GXTP5100", b"Goodix", b"GOODIX", b"LENOVO", b"Lenovo",
]

# Generic embedded-MCU vocabulary, for EC/firmware families that have nothing
# to do with haptics (e.g. the ITE/Compal PD+dock controller in this laptop's
# BIOS image scores 0 on KEYWORDS but plenty on this list).  Keeps the acceptor
# usable as a "did my decryption succeed?" oracle for ANY EC, while the
# haptic-specific vocabulary stays a separate, reported diagnostic.
KEYWORDS_MCU = [
    b"PORT80", b"ADC", b"PWM", b"UART", b"SMBus", b"SMB", b"TCPC", b"VDM",
    b"Sink", b"Source", b"Dock", b"Notify", b"Status", b"Volt", b"Curr",
    b"Cmd", b"CMD", b"Rd 0x", b"Wr 0x", b"Pass", b"Fail", b"Init", b"Reset",
    b"Timer", b"Duty", b"Boost", b"Charge", b"Batt", b"Therm", b"Fan",
    b"Sleep", b"Wake", b"Power", b"Enable", b"Disable", b"Error", b"Data",
    b"Version", b"Boot", b"Flash", b"Update", b"Commit", b"Config",
]


def entropy(buf: bytes) -> float:
    c = Counter(buf)
    n = len(buf)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def strings(buf: bytes, min_len: int = 6):
    return [m.group() for m in re.finditer(rb"[\x20-\x7e]{%d,}" % min_len, buf)]


IDENT_RE = re.compile(rb"[A-Za-z_][A-Za-z0-9_]{7,}")


def identifiers(buf: bytes):
    """DISTINCT identifier-like tokens (>= 8 chars, >= 3 distinct characters).

    Why distinct and not raw count: a single repeated byte written by a wrong
    transform produces one long run like 'RRRRRRRR' and would otherwise inflate
    the score.  Only a real string pool yields many DISTINCT names.
    Random data yields ~0.03/KiB; a firmware string pool yields ~0.4-1.5/KiB.
    This is the most discriminating metric between plaintext firmware and
    ciphertext.
    """
    out = set()
    for m in IDENT_RE.finditer(buf):
        t = m.group()
        if len(set(t)) >= 3:
            out.add(t)
    return out


def be_tables(buf: bytes, min_entries: int = 8, term=b"\x00" * 8):
    """Maximal runs of 8-byte big-endian (reg, value) groups, zero-terminated."""
    n = len(buf)
    tables = []
    i = 0
    while i + 8 <= n:
        j = i
        entries = 0
        while j + 8 <= n:
            reg = int.from_bytes(buf[j:j + 4], "big")
            if reg == 0 or reg > 0x04000000:
                break
            entries += 1
            j += 8
        if entries >= min_entries and buf[j:j + 8] == term:
            tables.append(dict(offset=i, entries=entries, end=j + 8))
            i = j + 8
        else:
            i += 1
    return tables


def wide_prefix_ratio(buf: bytes) -> float:
    """Thumb-2 32-bit instruction prefix density (top 5 bits >= 0b11101)."""
    n = len(buf) // 2
    if n == 0:
        return 0.0
    hit = 0
    for k in range(n):
        h = buf[2 * k] | (buf[2 * k + 1] << 8)
        if (h >> 11) >= 0x1D:
            hit += 1
    return hit / n


def measure(name: str, buf: bytes) -> dict:
    if not buf:
        return dict(name=name, size=0)
    kwh = {k.decode(): buf.count(k) for k in KEYWORDS}
    kwh = {k: v for k, v in kwh.items() if v}
    kwm = {k.decode(): buf.count(k) for k in KEYWORDS_MCU}
    kwm = {k: v for k, v in kwm.items() if v}
    tabs = be_tables(buf)
    m = dict(
        name=name,
        size=len(buf),
        H0=round(entropy(buf), 4),
        zero_pct=round(buf.count(0) / len(buf) * 100, 2),
        print_pct=round(sum(1 for b in buf if 0x20 <= b <= 0x7E) / len(buf) * 100, 2),
        strings=len(strings(buf)),
        str_per_kb=round(len(strings(buf)) / (len(buf) / 1024), 2),
        idents=len(identifiers(buf)),
        ident_per_kb=round(len(identifiers(buf)) / (len(buf) / 1024), 3),
        kw_hits=sum(kwh.values()),
        kw_top=dict(sorted(kwh.items(), key=lambda kv: -kv[1])[:8]),
        mcu_kw=sum(kwm.values()),
        mcu_top=dict(sorted(kwm.items(), key=lambda kv: -kv[1])[:8]),
        be_tables=len(tabs),
        be_max_entries=max((t["entries"] for t in tabs), default=0),
        wide_pct=round(wide_prefix_ratio(buf) * 100, 2),
    )
    m["ec_likeness"] = ec_likeness(m)
    return m


def ec_likeness(m: dict) -> int:
    """0..100.  Calibrated against four known bodies:
         SAM  body           -> plaintext MCU EC firmware      (must land >= 70)
         Touchpad body       -> encrypted code image           (must land < 25)
         Force body          -> dense data table, no code      (must land 25..45)
         Haptic body         -> DSP block table                (must land 25..45)
    Random/ciphertext scores ~0-10 because identifiers and reg tables are absent.
    """
    s = 0.0
    # haptic / EC-peripheral vocabulary -- the strongest single signal, but
    # only present if the firmware actually touches touchpad/haptics hardware
    s += 30 * max(0.0, min(1.0, m["kw_hits"] / 40))
    # generic embedded-MCU vocabulary -- domain-agnostic, so an EC whose job
    # is USB-PD / dock / thermal still scores as "plaintext firmware"
    s += 22 * max(0.0, min(1.0, m["mcu_kw"] / 60))
    # identifier-like token density (random data ~0.04/KiB, firmware ~0.5+/KiB)
    s += 18 * max(0.0, min(1.0, m["ident_per_kb"] / 0.5))
    # big-endian reg:value init tables terminated by 8 zero bytes
    s += 15 * max(0.0, min(1.0, m["be_max_entries"] / 50))
    # entropy must be below the ciphertext ceiling (8.0) but not table-low
    s += 10 * (1.0 if m["H0"] <= 6.9 else max(0.0, (7.6 - m["H0"]) / 0.7))
    # Thumb-2 wide-instruction density (weak: data tables score ~23% by chance)
    s += 5 * max(0.0, min(1.0, m["wide_pct"] / 20.0))
    # GATE: any real firmware names its own job somewhere.  With no vocabulary
    # at all the result may not be promoted above DATA/OPAQUE, whatever else.
    if m["kw_hits"] + m["mcu_kw"] < 5:
        s = min(s, 44.0)
    return round(s)


def verdict(m: dict) -> str:
    s = m.get("ec_likeness", 0)
    if s >= 70:
        return "PLAINTEXT-EC  明文 MCU 固件（可去反汇编）"
    if s >= 45:
        return "LIKELY-EC     疑似明文固件，值得人工看"
    if s >= 22:
        return "DATA/OPAQUE   数据表或半结构体，不是 EC 代码"
    return "CIPHER        仍处加密/加扰状态"


def fmt(m: dict) -> str:
    if not m.get("size"):
        return f"{m['name']:<44} <empty>"
    return (f"{m['name']:<44} {m['size']:>10,}B  H0={m['H0']:<7} "
            f"zero={m['zero_pct']:>6}%  print={m['print_pct']:>6}%  "
            f"str={m['strings']:<5}  ident={m['idents']:<5}({m['ident_per_kb']:>5}/KB) "
            f"kw={m['kw_hits']:<4} mcu={m['mcu_kw']:<4} be={m['be_tables']}/{m['be_max_entries']:<4} "
            f"wide={m['wide_pct']:>5}%  EC={m['ec_likeness']:>3}  {verdict(m)}")


def selftest(path: Path):
    """Falsification test: score a known-good plaintext firmware BEFORE and AFTER
    a reversible scramble.  If the acceptor does not collapse on the scrambled
    version, its verdicts are worthless -- so run this before trusting any score.
    """
    import random
    p = Path(path)
    if p.suffix.lower() == ".bin":
        found = unpack_capsule(p.read_bytes())
        buf = found[0]["body"] if found else p.read_bytes()
        label = found[0]["offer"][:4].hex() if found else "raw"
    else:
        buf = p.read_bytes()
        label = "raw"
    print(f"# selftest on {p.name} [{label}]  {len(buf):,} B\n")
    rows = [measure("  raw (expect PLAINTEXT-EC)", buf)]

    key = bytes(random.Random(1).randrange(256) for _ in range(1024))
    scr = bytes(b ^ key[i % 1024] for i, b in enumerate(buf))
    rows.append(measure("  XOR period-1024 (expect CIPHER)", scr))

    sh = bytearray(buf)
    rnd2 = random.Random(2)
    rnd2.shuffle(sh)
    rows.append(measure("  byte-shuffled (expect CIPHER)", bytes(sh)))

    rnd3 = random.Random(3)
    rows.append(measure("  uniform random (expect CIPHER)",
                        bytes(rnd3.randrange(256) for _ in range(len(buf)))))
    for m in rows:
        print(fmt(m))
    lo = max(m["ec_likeness"] for m in rows[1:])
    hi = rows[0]["ec_likeness"]
    print(f"\n  margin: plaintext {hi}  vs  best scrambled {lo}   ->  "
          f"{'OK' if hi - lo >= 40 else 'WEAK: tune weights'}")


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--capsule", action="append", default=[])
    ap.add_argument("--body", action="append", default=[])
    ap.add_argument("--overlay", action="append", default=[])
    ap.add_argument("--selftest", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    if a.selftest:
        return selftest(Path(a.selftest))

    rows = []
    for spec in a.capsule:
        p = Path(spec)
        for k, r in enumerate(unpack_capsule(p.read_bytes())):
            rows.append(measure(f"{p.name} [offer{k} {r['offer'][:4].hex()}]", r["body"]))
    for spec in a.body:
        p = Path(spec)
        rows.append(measure(p.name, p.read_bytes()))
    for spec in a.overlay:
        p = Path(spec)
        ov, note = extract_overlay(p)
        if ov is None:
            print(f"!! {p.name}: {note}")
            continue
        rows.append(measure(f"{p.name} [{note}]", ov))

    for m in rows:
        print(fmt(m))
        if m.get("kw_top"):
            print(f"    kw: {m['kw_top']}")

    if a.json:
        import json
        Path(a.json).write_text(json.dumps(rows, indent=1, ensure_ascii=False),
                                encoding="utf-8")
        print(f"\n-> {a.json}")


if __name__ == "__main__":
    sys.exit(main())
