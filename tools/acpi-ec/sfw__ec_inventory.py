#!/usr/bin/env python3
"""Build the EC-side inventory of touchpad and haptic identifiers.

The SAM body carries several NUL-terminated string pools. Grouping the whole
vocabulary by subsystem answers "what form does the touchpad / haptic control
surface take inside the EC" without needing the reader to open any other file:
every string is printed in full, grouped, and both variants are diffed so
variant-specific names are visible.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SAM = HERE / "out" / "SurfaceSAM_9.101.139"

# Subsystem grouping. A string lands in the first group whose keyword matches,
# so order matters: put the specific before the general.
GROUPS = (
    ("触觉执行链", ("actuate", "haptic", "vibegen", "waveform", "wseq", "boost", "buck")),
    ("触控板设备与任务", ("touchpad", "trackpad", "tp_", "force_sensor", "temperature")),
    ("I2C 总线与模块", ("i2c", "module")),
    ("信号引脚", ("scl", "sda", "_int", "_rst", "ts_spi", "clk", "miso", "mosi", "reset#")),
    ("固件升级与 Flash", ("fwupdate", "write_fw", "exit_fw", "flash", "exit")),
    ("模式与调试配置", ("mode", "debug", "dbg", "jtag", "spi_mode")),
    ("HID / 报告通道", ("hid", "report", "descriptor")),
    ("SSH 内部通道", ("ssh", "surflink", "queue", "evt", "task", "timer")),
    ("状态机", ("bck", "state", "bpm", "action", "reset")),
)


def load(variant: int) -> list[dict]:
    """Read the string list, tolerating either producer's key naming.

    `sam_strings.py` writes body_offset/runtime, `unpack_all.py` writes offset,
    and both write into the same directory, so accept either.
    """
    p = SAM / f"strings_{variant}.json"
    data = json.load(open(p, encoding="utf-8"))
    out = []
    for d in data:
        off = d.get("body_offset", d.get("offset"))
        if off is None:
            continue
        rt = d.get("runtime", off + 0x80000)
        out.append(dict(offset=f"0x{off:05X}", runtime=f"0x{rt:06X}", text=d["text"]))
    return out


def classify(strings: list[dict]) -> dict[str, list[dict]]:
    out = {name: [] for name, _ in GROUPS}
    unmatched = []
    for s in strings:
        low = s["text"].lower()
        for name, keys in GROUPS:
            if any(k in low for k in keys):
                out[name].append(s)
                break
        else:
            # only keep unmatched strings that look like real identifiers
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{5,}", s["text"]):
                unmatched.append(s)
    out["__unmatched__"] = unmatched
    return out


def main():
    report = {}
    for variant in (0, 1):
        strings = load(variant)
        groups = classify(strings)
        report[f"variant_{variant}"] = {
            k: [s["text"] for s in v] for k, v in groups.items()}

        print(f"=== variant {variant}: {len(strings)} strings total")
        for name, _ in GROUPS:
            items = groups[name]
            if not items:
                continue
            print(f"\n  [{name}]  {len(items)}")
            for s in items[:34]:
                print(f"    {s['runtime']}  {s['text']}")
            if len(items) > 34:
                print(f"    ... +{len(items) - 34} more")
        print()

    a = {s["text"] for s in load(0)}
    b = {s["text"] for s in load(1)}
    print(f"only variant 0 ({len(a - b)}): {sorted(a - b)}")
    print(f"only variant 1 ({len(b - a)}): {sorted(b - a)}")
    report["diff"] = dict(only_variant0=sorted(a - b), only_variant1=sorted(b - a),
                          shared=len(a & b))

    (SAM / "ec_inventory.json").write_text(json.dumps(report, indent=1),
                                           encoding="utf-8")


if __name__ == "__main__":
    main()
