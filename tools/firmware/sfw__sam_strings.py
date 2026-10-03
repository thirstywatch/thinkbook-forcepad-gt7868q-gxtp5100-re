#!/usr/bin/env python3
"""Dump every printable string in a SAM body and classify the haptic/touchpad set.

The SAM bodies embed several string pools that are plain NUL-terminated ASCII
with one to three NUL bytes of padding and *no* fixed stride -- an earlier
assumption of 16-byte records does not survive contact with the bytes, so this
walks runs instead of indexing.

The interesting content is the touchpad and haptic vocabulary: device names,
bus names, state names and the I2C addresses SAM uses to reach the CS40L25 and
the Buck/Boost regulator.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SAM = HERE / "out" / "SurfaceSAM_9.101.139"
LOAD_BASE = 0x80000

# Vocabulary that matters for the touchpad / haptic path, with why.
INTEREST = {
    "haptic": "haptic / CS40L25 driver path",
    "haptics": "haptic (plural)",
    "actuate": "actuator invocation entry point",
    "vibegen": "VIBEGEN waveform generator",
    "waveform": "waveform control",
    "wseq": "CS40L25 wave sequencer",
    "boost": "Buck/Boost rail (MP28167 on the ESP32 replica)",
    "buck": "Buck rail",
    "force": "force sensor",
    "pressure": "pressure sensing",
    "touchpad": "touchpad device",
    "trackpad": "trackpad device",
    "touch": "touch",
    "tp_": "touchpad-prefixed signal",
    "i2c": "I2C bus",
    "spi": "SPI bus",
    "sam_": "SAM internal mode/config",
    "flash": "external flash image slots",
    "mailbox": "DSP mailbox",
    "dsb": "device-side driver label",
    "d0": "feature report ID",
    "intensity": "haptic intensity setting",
    "click": "click / press feedback",
    "gesture": "gesture",
    "ptp": "precision touchpad",
    "hid": "HID transport",
    "ssh": "SAM communication channel",
    "fw": "firmware",
    "slot": "flash slot",
}


def all_strings(body: bytes, min_len: int = 4) -> list[dict]:
    return [dict(body_offset=m.start(), runtime=m.start() + LOAD_BASE,
                 text=m.group().decode("ascii"))
            for m in re.finditer(rb"[\x20-\x7e]{%d,}" % min_len, body)]


def pools(strings: list[dict], gap: int = 8) -> list[dict]:
    """Group strings into contiguous pools (consecutive NUL-terminated entries)."""
    out = []
    for s in strings:
        end = s["body_offset"] + len(s["text"]) + 1  # include one NUL
        if out and s["body_offset"] - out[-1]["_end"] <= gap:
            out[-1]["items"].append(s)
            out[-1]["_end"] = end
        else:
            out.append(dict(start=s["body_offset"], items=[s], _end=end))
    for p in out:
        p["size"] = p["_end"] - p["start"]
        p["runtime_start"] = f"0x{p['start'] + LOAD_BASE:06X}"
        p.pop("_end")
    return out


def classify(strings: list[dict]) -> list[dict]:
    hits = []
    for s in strings:
        low = s["text"].lower()
        tags = sorted({why for key, why in INTEREST.items() if key in low})
        if tags:
            hits.append(dict(**s, tags=tags))
    return hits


def main():
    summary = {}
    for variant in (0, 1):
        body = (SAM / f"body_{variant}.bin").read_bytes()
        strings = all_strings(body)
        pl = pools(strings)
        hot = classify(strings)
        (SAM / f"strings_{variant}.json").write_text(json.dumps(strings, indent=1),
                                                     encoding="utf-8")
        (SAM / f"haptic_strings_{variant}.json").write_text(
            json.dumps(hot, indent=1), encoding="utf-8")
        summary[f"variant_{variant}"] = dict(
            total_strings=len(strings), pool_count=len(pl),
            largest_pools=sorted([dict(start=f"0x{p['start']:X}", size=p["size"],
                                       count=len(p["items"])) for p in pl],
                                 key=lambda x: -x["size"])[:6],
            haptic_and_touchpad_strings=len(hot))
        print(f"=== variant {variant}")
        print(f"  total strings {len(strings)}  pools {len(pl)}  "
              f"haptic/touchpad-tagged {len(hot)}")
        for p in sorted(pl, key=lambda x: -x["size"])[:4]:
            print(f"    pool @0x{p['start']:05X} size {p['size']} entries {len(p['items'])}")
        print()

    # Side-by-side: strings unique to each variant, restricted to the tagged set.
    a = {(s["text"]) for s in json.load(open(SAM / "strings_0.json", encoding="utf-8"))}
    b = {(s["text"]) for s in json.load(open(SAM / "strings_1.json", encoding="utf-8"))}
    only0 = sorted(a - b)
    only1 = sorted(b - a)
    print(f"strings only in variant 0: {len(only0)}")
    print(f"strings only in variant 1: {len(only1)}")
    (SAM / "string_diff.json").write_text(
        json.dumps(dict(only_variant0=only0, only_variant1=only1,
                        shared=len(a & b)), indent=1), encoding="utf-8")
    (SAM / "string_summary.json").write_text(json.dumps(summary, indent=1),
                                              encoding="utf-8")

    print("\n-- haptic / touchpad vocabulary (variant 0, first 70) --")
    hot = json.load(open(SAM / "haptic_strings_0.json", encoding="utf-8"))
    for s in hot[:70]:
        print(f"  0x{s['body_offset']:05X} (rt {s['runtime']:06X})  {s['text']}")
    print(f"  ... total {len(hot)}")


if __name__ == "__main__":
    main()
