#!/usr/bin/env python3
"""Unpack every Surface firmware capsule and dump a full structural report.

Produces, under analysis/out/:
  <name>/component_<i>.bin   reassembled Component per CFU offer
  <name>/body_<i>.bin        body after the Component header
  <name>/offer_<i>.bin       raw 16-byte offer
  <name>/cfu_payload_<i>.bin framed CFU record stream
  <name>/report.json         every offset, length, hash and invariant
  <name>/strings.json        printable runs found in the body

Nothing here talks to hardware, and no signature is verified: the cert blob is
preserved for offline checking.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from surface_capsule import Capsule, cs40l25_blocks, load, require, sha, take, unpack  # noqa: E402

HERE = Path(__file__).resolve().parent
FW = HERE.parent / "firmware"
OUT = HERE / "out"

# SAM carries two *different* variants; the three touchpad capsules carry two
# byte-identical copies of the same payload.
IDENTICAL_EXPECTED = {
    "SurfaceSAM_9.101.139.bin": False,
    "SurfaceTouchpad_4.12.139.bin": True,
    "SurfaceTouchpadForce_10.0.156.bin": True,
    "SurfaceTouchpadHaptic_2.9.139.bin": True,
}


def strings_report(body: bytes, min_len: int = 5) -> list[dict]:
    out = []
    for m in re.finditer(rb"[\x20-\x7e]{%d,}" % min_len, body):
        out.append(dict(offset=m.start(), text=m.group().decode("ascii")))
    return out


def analyze(path: Path) -> dict:
    name = path.name
    print(f"\n=== {name}")
    cap = load(path, name)
    cfu = cap.split()
    pairs = cap.parse_cfu(cfu, require_identical=IDENTICAL_EXPECTED.get(name, True))

    dest = OUT / path.stem
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "signature.p7b").write_bytes(cap.signature)

    report = dict(name=name, meta=cap.meta, variants=[])
    print(f"  capsule {cap.meta['capsule_size']:,} B  flags={cap.meta['capsule_flags']}  "
          f"mss1={cap.meta['mss1_version']}  cfu@{cap.meta['cfu_offset']:#x}")
    print(f"  offers={len(pairs)}  identical={IDENTICAL_EXPECTED.get(name)}")

    for i, p in enumerate(pairs):
        (dest / f"offer_{i}.bin").write_bytes(p["offer"])
        (dest / f"cfu_payload_{i}.bin").write_bytes(p["payload"])
        (dest / f"component_{i}.bin").write_bytes(p["image"])
        comp = p["image"]
        cinfo = Capsule.parse_component(comp)
        body = comp[cinfo["body_offset"]:]
        (dest / f"body_{i}.bin").write_bytes(body)

        v = dict(index=i, offer=p["offer"].hex(), offer_offset=p["offer_offset"],
                 cfu_records=len(p["records"]), cfu_payload_bytes=len(p["payload"]),
                 component_bytes=len(comp), component_sha256=sha(comp),
                 **cinfo, body_sha256=sha(body),
                 body_first16=body[:16].hex())
        report["variants"].append(v)
        print(f"  [{i}] offer={p['offer'].hex()}")
        print(f"      records={len(p['records'])} component={len(comp):,} "
              f"body@{cinfo['body_offset']:#x} body={len(body):,}")

        # Touchpad haptic bodies carry the CS40L25 download-block table; the
        # others are opaque firmware images, so parsing is attempted, not assumed.
        if len(body) >= 8:
            rev, count = unpack("<II", body, 0)
            if rev == 0x02800010 and 0 < count < 4096:
                try:
                    blocks = cs40l25_blocks(body)
                except ValueError as exc:
                    v["cs40l25_blocks"] = f"parse failed: {exc}"
                else:
                    v["cs40l25"] = dict(
                        block_count=len(blocks),
                        address_min=min(a for _, a, _ in blocks),
                        address_max=max(a for _, a, _ in blocks),
                        payload_bytes=sum(len(d) for _, _, d in blocks),
                        core_blocks=sum(1 for s, _, _ in blocks if s < 137),
                        appended_blocks=sum(1 for s, _, _ in blocks if s >= 137),
                    )
                    (dest / f"haptic_blocks_{i}.json").write_text(json.dumps(
                        [dict(sequence=s, address=a, length=len(d),
                              crc16=__import__("binascii").crc_hqx(d, 0xFFFF),
                              sha256=sha(d)) for s, a, d in blocks], indent=1),
                        encoding="utf-8")
                    print(f"      CS40L25 blocks={len(blocks)} "
                          f"addr={v['cs40l25']['address_min']:#010x}.."
                          f"{v['cs40l25']['address_max']:#010x} "
                          f"core/appended={v['cs40l25']['core_blocks']}/"
                          f"{v['cs40l25']['appended_blocks']}")

        strs = strings_report(body)
        if strs:
            (dest / f"strings_{i}.json").write_text(json.dumps(strs, indent=1),
                                                    encoding="utf-8")
            v["string_count"] = len(strs)
            v["printable_ratio"] = round(sum(len(s["text"]) for s in strs) / len(body), 4)
            print(f"      strings={len(strs)} printable={v['printable_ratio']:.2%}")

    (dest / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for path in sorted(FW.glob("*.bin")):
        analyze(path)


if __name__ == "__main__":
    main()
