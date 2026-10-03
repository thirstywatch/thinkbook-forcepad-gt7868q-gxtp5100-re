#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Extract the observed Synaptics RMI image and decode the CS40L25 wake sequence.

Offline only. Container IDs/layout follow Linux rmi_f34.h; private container
relationships are explicitly labelled as sample observations. No decryption,
hardware updater, or recovered host source code is claimed.
"""
from __future__ import annotations

import argparse
import csv
import math
import re
import struct
from collections import Counter
from pathlib import Path

from extract_surface import (REPO, REFERENCE, coalesce, parse_capsule,
                             parse_cfu_pairs, parse_component, parse_haptic,
                             require, sdk_blocks, sha, take, unpack, write_json)

CONTAINERS = {
    0: "TOP_LEVEL", 1: "UI", 2: "UI_CONFIG", 3: "BOOTLOADER",
    4: "BOOTLOADER_IMAGE", 5: "BOOTLOADER_CONFIG", 6: "BL_LOCKDOWN_INFO",
    7: "PERMANENT_CONFIG", 8: "GUEST_CODE", 9: "BL_PROTOCOL_DESCRIPTOR",
    10: "UI_PROTOCOL_DESCRIPTOR", 11: "RMI_SELF_DISCOVERY",
    12: "RMI_PAGE_CONTENT", 13: "GENERAL_INFORMATION", 14: "DEVICE_CONFIG",
    15: "FLASH_CONFIG", 16: "GUEST_SERIALIZATION", 17: "GLOBAL_PARAMETERS",
    18: "CORE_CODE", 19: "CORE_CONFIG", 20: "DISPLAY_CONFIG",
}


def rmi_checksum(data):
    """16-bit LE Fletcher with end-around carry and FFFF initial accumulators.

    The observed odd-length page containers checksum an implicit zero high byte.
    Preserve the FFFF representation of zero (unlike modulo-only arithmetic).
    """
    data = bytes(data) + (b"\0" if len(data) % 2 else b"")
    first = second = 0xFFFF
    for (word,) in struct.iter_unpack("<H", data):
        first += word
        first = (first & 0xFFFF) + (first >> 16)
        second += first
        second = (second & 0xFFFF) + (second >> 16)
    return second << 16 | first


def parse_rmi(image):
    checksum, = unpack("<I", image, 0)
    require(take(image, 6, 2) == b"\x00\x10", "Expected RMI image header 0x10.0")
    require(checksum == rmi_checksum(image[4:]), "RMI image checksum mismatch")
    root, = unpack("<I", image, 12)
    records, seen = [], set()

    def visit(offset, parent=None, expected=None, relation="standard container pointer"):
        require(offset not in seen, "Repeated/cyclic RMI container pointer")
        require(len(seen) < 128, "Too many RMI containers")
        seen.add(offset)
        fields = unpack("<IHBB6I", image, offset)
        check, kind, minor, major, reserved, flags, olen, oa, size, address = fields
        require(expected is None or kind == expected, "Unexpected RMI child container type")
        data = take(image, address, size)
        if olen:
            take(image, oa, olen)
        require(check == rmi_checksum(data), f"RMI container {offset:#x} checksum mismatch")
        name = CONTAINERS.get(kind, f"UNKNOWN_{kind:02X}")
        row = dict(descriptor_offset=offset, parent_descriptor_offset=parent,
                   relationship=relation, container_id=kind, name=name,
                   major_version=major, minor_version=minor, reserved=reserved,
                   option_flags=flags, options_offset=oa, options_size=olen,
                   content_offset=address, content_size=size, checksum=f"0x{check:08x}",
                   checksum_verified=True, sha256=sha(data),
                   output_file=f"containers/{offset:06x}_{name}.bin")
        records.append(row)
        skip = None
        child_type = None
        if kind in (0, 11):
            skip = 0
            child_type = 12 if kind == 11 else None
        elif kind == 3:
            require(size >= 4, "Truncated bootloader container")
            row["bootloader_version_bytes"] = data[:4].hex()
            skip = 4
        elif kind == 0x18:
            # Observed sample: a single pointer to a type-0x19 descriptor.
            # Do not assign a vendor name/semantics to either private ID.
            require(size == 4, "Unknown private 0x18 layout")
            skip, child_type = 0, 0x19
        if skip is not None:
            require((size - skip) % 4 == 0, "Unaligned container pointer list")
            for (child,) in struct.iter_unpack("<I", data[skip:]):
                visit(child, offset, child_type,
                      "observed private 0x18 -> 0x19 pointer" if kind == 0x18
                      else "observed RMI page pointer" if kind == 11
                      else "standard container pointer")

    visit(root, expected=0)
    info = next(r for r in records if r["container_id"] == 13)
    content = take(image, info["content_offset"], info["content_size"])
    require(len(content) >= 34, "Truncated general information")
    product = take(content, 24, 10).decode("ascii")
    product_text = re.match(rb"[ -~]+", content[24:]).group().decode("ascii")
    fw_id, = unpack("<I", content, 4)
    return dict(format="Synaptics RMI image header 0x10", image_size=len(image),
                image_sha256=sha(image), image_checksum=f"0x{checksum:08x}",
                image_checksum_verified=True, product_id=product,
                observed_product_ascii_run=product_text, firmware_id=fw_id,
                firmware_id_hex=f"0x{fw_id:08x}", containers=records,
                flash_compatibility="not tested; requires matching hardware and updater")


def decode_wseq(data):
    """Invert the byte layout in cs40l25_wseq_entry_t, preserving duplicates."""
    rows = []
    offset = 0
    while offset < len(data):
        first = take(data, offset, 4)
        if first == b"\x00\xff\xff\xff":
            require(offset + 4 == len(data), "Trailing data after WSEQ terminator")
            return rows
        raw = take(data, offset, 8)
        require(raw[0] == raw[4] == 0, "Unsupported WSEQ reserved bits/opcode")
        address = int.from_bytes(raw[1:3], "big")
        value = int.from_bytes(raw[3:4] + raw[5:8], "big")
        rows.append(dict(index=len(rows), sequence_byte_offset=offset,
                         register_address=address, register_hex=f"0x{address:04x}",
                         value=value, value_hex=f"0x{value:08x}", raw_hex=raw.hex()))
        offset += 8
    raise ValueError("Missing WSEQ terminator")


def encode_wseq(rows):
    result = bytearray()
    for row in rows:
        a = row["register_address"].to_bytes(2, "big")
        v = row["value"].to_bytes(4, "big")
        result.extend(b"\0" + a + v[:1] + b"\0" + v[1:])
    return bytes(result) + b"\x00\xff\xff\xff"


def register_names():
    text = (REPO / "cs40l25/cs40l25_spec.h").read_text(encoding="utf-8")
    names = {}
    for name, address in re.findall(r"^#define\s+(\w+_REG)\s+\((0[xX][0-9a-fA-F]+)\)", text, re.M):
        names.setdefault(int(address, 16), []).append(name)
    return names


def export_analysis(input_dir, output):
    require(output.resolve() != input_dir.resolve(), "Use a separate output directory")
    sources = {}
    for filename in ("SurfaceTouchpad_4.12.139.bin", "SurfaceTouchpadForce_10.0.156.bin",
                     "SurfaceTouchpadHaptic_2.9.139.bin"):
        raw = (input_dir / filename).read_bytes()
        meta, _, _, cfu = parse_capsule(raw)
        image = parse_cfu_pairs(cfu)[0]["image"]
        component = parse_component(image)
        sources[filename] = (raw, image, component, meta)
    touch = sources["SurfaceTouchpad_4.12.139.bin"]
    rmi = touch[1][touch[2]["body_offset"]:]
    syn = parse_rmi(rmi)
    syn["source_component_body_offset"] = touch[2]["body_offset"]
    syn_dir = output / "synaptics"
    (syn_dir / "containers").mkdir(parents=True, exist_ok=True)
    filename = f"{syn['product_id']}_Surface_4.12.139.img"
    (syn_dir / filename).write_bytes(rmi)
    syn["image_file"] = filename
    for row in syn["containers"]:
        data = take(rmi, row["content_offset"], row["content_size"])
        (syn_dir / row["output_file"]).write_bytes(data)
        if row["container_id"] in (4, 18):
            counts = Counter(data)
            row["shannon_entropy_bits_per_byte"] = -sum(
                n / len(data) * math.log2(n / len(data)) for n in counts.values())
    write_json(syn_dir / "manifest.json", syn)

    haptic = sources["SurfaceTouchpadHaptic_2.9.139.bin"]
    blocks = parse_haptic(haptic[1][haptic[2]["body_offset"]:])
    _, reference = sdk_blocks(REFERENCE)
    require(reference == [(b["address"], b["data"]) for b in blocks[:len(reference)]],
            "CS40L25 core reference mismatch")
    regions = coalesce(blocks[len(reference):])
    require([a for a, _ in regions] == [0x02800B60, 0x03400000, 0x028016D0],
            "Unexpected tuning regions")
    sequence = regions[-1][1]
    rows = decode_wseq(sequence)
    require(encode_wseq(rows) == sequence, "WSEQ round-trip mismatch")
    names = register_names()
    for row in rows:
        row["sdk_register_names"] = names.get(row["register_address"], [])
    ctl_dir = output / "cs40l25_control"
    ctl_dir.mkdir(parents=True, exist_ok=True)
    (ctl_dir / "power_on_sequence.bin").write_bytes(sequence)
    write_json(ctl_dir / "power_on_sequence.json", dict(
        source_dsp_address="0x028016d0", size=len(sequence), sha256=sha(sequence),
        entries=len(rows), terminator_offset=len(sequence) - 4, round_trip_verified=True,
        reference_metadata_length=388, sdk_host_wseq_capacity=48,
        limitation="56-entry sample exceeds reference 48-entry metadata/host table; reconcile before hardware use",
        writes=rows))
    with (ctl_dir / "power_on_sequence.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["index", "sequence_offset", "register", "value", "sdk_name"])
        for row in rows:
            writer.writerow([row["index"], f"0x{row['sequence_byte_offset']:x}",
                             row["register_hex"], row["value_hex"], ";".join(row["sdk_register_names"])])
    write_json(ctl_dir / "dsp_download_writes.json", [dict(
        index=b["index"], address=f"0x{b['address']:08x}", size=b["size"],
        crc16=f"0x{b['crc16']:04x}", data_hex=b["data"].hex()) for b in blocks])

    force = sources["SurfaceTouchpadForce_10.0.156.bin"]
    body = force[1][force[2]["body_offset"]:]
    force_dir = output / "force"
    force_dir.mkdir(parents=True, exist_ok=True)
    (force_dir / "SurfaceForce_10.0.156.body.bin").write_bytes(body)
    # Candidate vector table: evidence for subsequent disassembly, not a CPU ID.
    stack, reset = unpack("<II", body, 0x14)
    write_json(force_dir / "inspection.json", dict(
        size=len(body), sha256=sha(body), body_offset_in_component=force[2]["body_offset"],
        candidate_vector_offset="0x14", candidate_initial_stack=f"0x{stack:08x}",
        candidate_reset_vector=f"0x{reset:08x}",
        interpretation="Thumb/Cortex-M-like vector and instruction pattern; exact chip/load map unconfirmed",
        synaptics_rmi_image=False, host_haptic_logic="not recovered"))

    summary = dict(sources=[dict(file=n, size=len(v[0]), sha256=sha(v[0]))
                            for n, v in sources.items()],
                   synaptics_image=f"synaptics/{filename}", rmi_containers=len(syn["containers"]),
                   rmi_checksum_verified=True, cs40l25_wseq_entries=len(rows),
                   cs40l25_wseq_round_trip_verified=True,
                   signatures="not reverified by this analysis; see extraction manifest",
                   hardware_tested=False, original_host_source_recovered=False)
    for name, value in sources.items():
        require((input_dir / name).read_bytes() == value[0], "Original input changed")
    write_json(output / "manifest.json", summary)
    write_json(output / "SHA256SUMS.json", {
        p.relative_to(output).as_posix(): sha(p.read_bytes())
        for p in sorted(output.rglob("*")) if p.is_file() and p.name != "SHA256SUMS.json"})
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=REPO / "targetbin")
    parser.add_argument("--output-dir", type=Path, default=REPO / "targetbin/component_analysis")
    args = parser.parse_args()
    print(export_analysis(args.input_dir, args.output_dir))


if __name__ == "__main__":
    main()
