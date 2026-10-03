#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Extract and annotate the two observed SurfaceSAM 9.101.139 host firmware variants.

The ELF files are analysis wrappers, not original build artifacts or flash images.
Addresses use the 0x80000 mapping corroborated by startup VTOR and pointer references.
"""
import argparse
import io
import re
import shutil
import struct
import subprocess
from pathlib import Path

from extract_surface import (REPO, parse_capsule, parse_component, parse_haptic,
                             require, sha, take, unpack, write_json)

BASE = 0x80000
FUNCTIONS = [
    (0x903F8, 0x90404, "bus_write_wrapper"),
    (0x90414, 0x90420, "bus_write_read_wrapper"),
    (0xD82E2, 0xD82F8, "select_register_init_table"),
    (0xD8318, 0xD83B8, "platform_initialize_caller_partial"),
    (0xDC530, 0xDC5BE, "ActuateHaptic_named_object_setup_and_callback"),
    (0xDCB5C, 0xDCBA8, "pre_download_prepare"),
    (0xDCBA8, 0xDCBC0, "enable_dsp_core"),
    (0xDCBC0, 0xDCC4E, "write_descriptor_array"),
    (0xDCC4E, 0xDCCC4, "download_builtin_firmware"),
    (0xDCCC4, 0xDCD54, "write_external_image_block"),
    (0xDCD54, 0xDCDB8, "download_external_image"),
    (0xDCDB8, 0xDCDFA, "apply_register_init_table"),
    (0xDCDFA, 0xDCF90, "initialize_haptic_device"),
    (0xDCF92, 0xDCFD8, "read_dsp_word_0280000c"),
    (0xDCFD8, 0xDCFF2, "trigger_mailbox_index"),
    (0xDCFF2, 0xDD048, "mask_irqs_and_mailbox_command_1"),
    (0xDD048, 0xDD086, "mailbox_command_2_and_restore_irq_mask"),
    (0xDD086, 0xDD0A0, "set_control_0280167c"),
    (0xDD0A0, 0xDD0BA, "set_control_0280168c"),
    (0xDD0BA, 0xDD148, "command_and_read_scaled_02802b08"),
    (0xE1AA8, 0xE1ACE, "external_image_read_block_count"),
    (0xE1ACE, 0xE1AF4, "external_image_read_first_header_word"),
    (0xE1AF4, 0xE1B1E, "external_image_read_14_byte_block_header"),
    (0xE1B1E, 0xE1B94, "external_image_read_block_data"),
]


def parse_sam_pairs(cfu):
    pairs = []
    pos = 0
    for index in range(2):
        offer_offset = pos
        offer = take(cfu, pos, 16)
        expected = bytes.fromhex("020000b08b6500090100000004023c00")
        if index:
            expected = expected[:12] + b"\x14" + expected[13:]
        require(offer == expected, "Unsupported SAM offer")
        pos += 16
        start = pos
        image = bytearray()
        count = 0
        while pos < len(cfu):
            address, length = unpack("<IB", cfu, pos)
            if not 0 < length <= 16:
                break
            require(address == len(image), "SAM CFU gap/overlap/order error")
            image.extend(take(cfu, pos + 5, length))
            pos += 5 + length
            count += 1
        component = parse_component(image)
        require(component["body_size"] == 524288, "Unexpected SAM body size")
        pairs.append(dict(offer=offer, offer_offset=offer_offset, records=count,
                          payload=cfu[start:pos], image=bytes(image), component=component))
    require(pos == len(cfu), "Unexpected trailing SAM CFU data")
    # These are distinct variants, not redundant copies. Do not deduplicate.
    return pairs


def make_elf(body):
    require(len(body) == 0x80000, "Expected 512 KiB SAM image")
    entry, = unpack("<I", body, 4)
    require(BASE <= (entry & ~1) < BASE + len(body) and entry & 1, "Invalid Thumb entry")
    names = b"\0.text\0.shstrtab\0"
    offset = 0x1000
    strings = offset + len(body)
    sections = (strings + len(names) + 3) & ~3
    elf = bytearray(sections + 120)
    ident = b"\x7fELF\x01\x01\x01" + bytes(9)
    struct.pack_into("<16sHHIIIIIHHHHHH", elf, 0, ident, 2, 40, 1, entry, 52, sections,
                     0x05000000, 52, 32, 1, 40, 3, 2)
    struct.pack_into("<IIIIIIII", elf, 52, 1, offset, BASE, BASE, len(body), len(body), 5, 0x1000)
    elf[offset:strings] = body
    elf[strings:strings + len(names)] = names
    struct.pack_into("<IIIIIIIIII", elf, sections + 40, 1, 1, 6, BASE, offset, len(body), 0, 0, 4, 0)
    struct.pack_into("<IIIIIIIIII", elf, sections + 80, 7, 3, 0, 0, strings, len(names), 0, 0, 1, 0)
    return bytes(elf)


def descriptor_groups(body):
    records = []
    for offset in range(0, len(body) - 11, 4):
        size, address, pointer = unpack("<III", body, offset)
        if not (0 < size <= 240 and size % 4 == 0 and BASE <= pointer <= BASE + len(body) - size):
            continue
        if not any(lo <= address and address + size <= hi for lo, hi in
                   [(0x02000000, 0x02400000), (0x02800000, 0x03000000), (0x03400000, 0x03C00000)]):
            continue
        data = take(body, pointer - BASE, size)
        records.append(dict(descriptor_offset=offset, descriptor_address=BASE + offset,
                            size=size, dsp_address=address, source_pointer=pointer,
                            sha256=sha(data), data_hex=data.hex()))
    groups = []
    for row in records:
        if not groups or row["descriptor_offset"] != groups[-1][-1]["descriptor_offset"] + 12:
            groups.append([])
        groups[-1].append(row)
    require([len(group) for group in groups] == [137, 11, 2], "Unexpected SAM DSP table layout")
    return groups


def register_table(body, offset):
    rows = []
    for index in range(128):
        raw = take(body, offset + index * 8, 8)
        address, value = struct.unpack(">II", raw)
        if (address, value) == (0, 0):
            return rows
        rows.append(dict(index=index, source_offset=offset + index * 8,
                         register=f"0x{address:08x}", value=f"0x{value:08x}", wire_hex=raw.hex()))
    raise ValueError("Missing init table terminator")


def annotate(body, text):
    lines = []
    for line in text.splitlines():
        match = re.search(r"ldr(?:\.w)?\s+\w+, \[pc.*@ 0x([0-9a-f]+)", line)
        if match:
            offset = int(match.group(1), 16) - BASE
            if 0 <= offset <= len(body) - 4:
                value, = unpack("<I", body, offset)
                line += f" ; literal=0x{value:08x}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def analyze(source, output):
    raw = source.read_bytes()
    capsule, signature, signed, cfu = parse_capsule(raw)
    pairs = parse_sam_pairs(cfu)
    output.mkdir(parents=True, exist_ok=True)
    # Unlike the older touchpad packages, this sample already has ContentInfo.
    require(bytes.fromhex("06092a864886f70d010702") in signature[:32], "Expected complete CMS ContentInfo")
    (output / "signature.p7b").write_bytes(signature)
    (output / "signed_content.bin").write_bytes(signed)
    verification = "not attempted"
    openssl = shutil.which("openssl")
    if openssl:
        result = subprocess.run([openssl, "cms", "-verify", "-binary", "-inform", "DER",
                                 "-in", str(output / "signature.p7b"), "-content", str(output / "signed_content.bin"),
                                 "-noverify", "-out", str(output / "verified_signed_content.bin")], capture_output=True)
        (output / "signature_verification.log").write_bytes(result.stdout + result.stderr)
        require(result.returncode == 0, "SAM signature verification failed")
        verification = "valid detached signature; certificate trust not evaluated"
    haptic = parse_haptic((REPO / "targetbin/unpacked/SurfaceTouchpadHaptic_2.9.139/component.body.bin").read_bytes())
    summaries = []
    for index, pair in enumerate(pairs):
        image = pair["image"]
        body = image[pair["component"]["body_offset"]:]
        (output / f"component_{index}.bin").write_bytes(image)
        (output / f"body_{index}.bin").write_bytes(body)
        (output / f"offer_{index}.bin").write_bytes(pair["offer"])
        elf = output / f"body_{index}.analysis.elf"
        elf.write_bytes(make_elf(body))
        groups = descriptor_groups(body)
        from wmfw_parser import unpack_memory
        id_words = unpack_memory(io.BytesIO(bytes.fromhex(groups[0][0]["data_hex"])), True, "p32", "u24")
        mismatches = []
        for n, row in enumerate(groups[0]):
            reference = haptic[n]
            require((row["dsp_address"], row["size"]) == (reference["address"], reference["size"]),
                    "SAM/Haptic core descriptor address or size differs")
            if bytes.fromhex(row["data_hex"]) != reference["data"]:
                mismatches.append(n)
        sequence = b"".join(bytes.fromhex(row["data_hex"]) for row in groups[2])
        expected_sequence = b"".join(block["data"] for block in haptic[165:])
        require(sequence == expected_sequence, "SAM and Haptic WSEQ differ")
        (output / f"body_{index}.wseq.bin").write_bytes(sequence)
        write_json(output / f"body_{index}.dsp_tables.json", dict(
            groups=[dict(count=len(rows), table_address=f"0x{rows[0]['descriptor_address']:08x}",
                         rows=rows) for rows in groups],
            mismatching_core_indices=mismatches, matching_core_count=137 - len(mismatches),
            wseq_matches_haptic=True, source_body_sha256=sha(body),
            builtin_firmware_id=f"0x{id_words[3]:06x}", builtin_firmware_revision=f"0x{id_words[4]:06x}"))
        strings = []
        for match in re.finditer(rb"[ -~]{5,}", body):
            if re.search(rb"haptic|touchpad|force_sensor", match.group(), re.I):
                offset = match.start()
                pointer = struct.pack("<I", BASE + offset)
                strings.append(dict(text=match.group().decode(), body_offset=offset,
                                    address=f"0x{BASE + offset:08x}",
                                    pointer_offsets=[m.start() for m in re.finditer(re.escape(pointer), body)]))
        write_json(output / f"body_{index}.strings.json", strings)
        objdump = shutil.which("llvm-objdump")
        if objdump:
            text = subprocess.check_output([objdump, "-d", "--triple=thumbv7m-none-eabi", str(elf)], text=True)
            annotated = annotate(body, text)
            (output / f"body_{index}.annotated.asm").write_text(annotated, encoding="utf-8")
            if index == 0:
                instructions = []
                for line in annotated.splitlines():
                    match = re.match(r"\s*([0-9a-f]+):", line)
                    if match:
                        instructions.append((int(match.group(1), 16), line))
                excerpts = ["; Analyst-assigned function names; SAM variant 0 only.\n"]
                for start, end, name in FUNCTIONS:
                    excerpts.append(f"\n; {name}: [0x{start:x}, 0x{end:x})\n")
                    excerpts.extend(line + "\n" for address, line in instructions if start <= address < end)
                (output / "reviewed_functions.asm").write_text("".join(excerpts), encoding="utf-8")
        summaries.append(dict(index=index, image_sha256=sha(image), body_sha256=sha(body),
                              body_size=len(body), body_offset=pair["component"]["body_offset"],
                              cfu_records=pair["records"], offer_hex=pair["offer"].hex(),
                              offer_file_offset=capsule["cfu_offset"] + pair["offer_offset"],
                              reset_vector=f"0x{unpack('<I', body, 4)[0]:08x}",
                              matching_core_count=137 - len(mismatches), mismatching_core_indices=mismatches,
                              wseq_matches_haptic=True))
    # Tables referenced by code in variant 0, selected by a platform selector.
    body0 = pairs[0]["image"][pairs[0]["component"]["body_offset"]:]
    write_json(output / "body_0.init_tables.json", [dict(
        table_address=f"0x{BASE + offset:08x}", writes=register_table(body0, offset))
        for offset in (0x41EC, 0x442C)])
    write_json(output / "reviewed_functions.json", [dict(
        analyst_name=name, start=f"0x{start:08x}", end_exclusive=f"0x{end:08x}",
        body_offset=start - BASE, sha256=sha(take(body0, start - BASE, end - start)))
        for start, end, name in FUNCTIONS])
    require(source.read_bytes() == raw, "Source SAM capsule changed")
    write_json(output / "manifest.json", dict(source=str(source), source_sha256=sha(raw),
               signature_verification=verification, variants=summaries,
               variants_identical=pairs[0]["image"] == pairs[1]["image"],
               analysis_load_base="0x00080000", hardware_execution=False,
               caution="Linear Thumb disassembly includes data and literal pools; use reviewed function ranges"))
    write_json(output / "SHA256SUMS.json", {p.name: sha(p.read_bytes()) for p in sorted(output.iterdir())
                                           if p.is_file() and p.name != "SHA256SUMS.json"})
    print(f"SAM: two distinct 512 KiB variants, signature={verification}, 137+11+2 DSP tables each")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, nargs="?", default=REPO / "surface/unpacked/payload/SurfaceUpdate/surfacesam/SurfaceSAM_9.101.139.bin")
    parser.add_argument("output", type=Path, nargs="?", default=REPO / "surface/analysis/sam")
    args = parser.parse_args()
    analyze(args.source, args.output)
