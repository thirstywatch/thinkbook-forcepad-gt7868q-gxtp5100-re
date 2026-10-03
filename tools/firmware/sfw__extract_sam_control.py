#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Offline evidence extraction for SurfaceSAM 9.101.139 CS40L25 control.

Recovered RAM codec is transcribed from Thumb 0x9527e (variant 0).
Names/ranges are analyst annotations, not recovered source symbols. Never flashes.
Only the two SHA-pinned samples are supported. Re-run analyze_sam.py first.
"""
import argparse
import bisect
import hashlib
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = 0x80000
HASHES = [
    "4f518e9a600ca7f08270498f01521199b6ec4408900a56bce515cf26f03e16c4",
    "6b088005f7419d9ae4f6bdb57a182db7dddc657b2e708793fcb1999ab2a3dce4",
]
# Regions intentionally include literal pools/context, and are not function sizes.
REGIONS = [
    (0xd6bd4, 0xd7e68, "touchpad_lifecycle_state_machine"),
    (0xd7e68, 0xd867c, "platform_context_gpio_policy"),
    (0xdc350, 0xdcb5c, "buckboost_state_machine"),
    (0xdcb5c, 0xdd1bc, "cs40l25_download_runtime"),
    (0xdd1bc, 0xdd7b0, "external_flash_slots"),
    (0xdf6a4, 0xdf930, "host_command_dispatch_context"),
    (0xd9400, 0xd94e0, "hid_report_dispatch_context"),
    (0xe1aa8, 0xe1bfc, "external_image_reader"),
    (0xe44b8, 0xe4688, "buckboost_i2c_control"),
    (0x90074, 0x90428, "bus_context_retry_wrappers"),
    (0x94282, 0x947b0, "i2c_transfer_context"),
    (0x98c24, 0x99100, "bus_device_initialization_context"),
    (0x8f810, 0x8fb28, "gpio_wrappers_context"),
    (0x91c9e, 0x91d24, "gpio_mmio_context"),
    (0x99e48, 0x9a080, "flash_access_context"),
    (0xd4204, 0xd4554, "touchpad_task_event_context"),
    (0xe6dcc, 0xe6e20, "startup_dispatch_context"),
    (0x9527e, 0x952fa, "startup_decompressor"),
]
FUNCTIONS = [
    (0xd6e7e, 0xd6ee2, "lifecycle_initialize_devices"),
    (0xd6ee2, 0xd6f14, "lifecycle_teardown_haptic"),
    (0xd6f14, 0xd6f56, "lifecycle_enter_deep_sleep"),
    (0xd6f56, 0xd6f98, "lifecycle_enter_normal"),
    (0xd8006, 0xd807c, "check_scaled_measurement_range"),
    (0xd7f0c, 0xd7fd0, "install_haptic_context"),
    (0xd80c2, 0xd8110, "cs_irq_enable_disable"),
    (0xd8194, 0xd81c4, "cs_irq_callback"),
    (0xd81c4, 0xd820c, "actuation_gpio_callback"),
    (0xd820c, 0xd823c, "boost_irq_callback"),
    (0xd8240, 0xd82e2, "set_power_gpio_mode"),
    (0xd8318, 0xd83de, "platform_initialize"),
    (0xd83e0, 0xd842a, "platform_teardown"),
    (0xd8430, 0xd845c, "platform_mailbox_command_2"),
    (0xd845c, 0xd847a, "external_storage_callback"),
    (0xd847a, 0xd84ae, "manual_trigger_power_bracket"),
    (0xd84b0, 0xd84f8, "read_gpio_timestamps_faults"),
    (0xd8530, 0xd8582, "set_intensity_setting"),
    (0xd8584, 0xd859a, "get_intensity_setting"),
    (0xd859a, 0xd85e8, "setting_to_two_indices"),
    (0xd85e8, 0xd8616, "probe_boost_id_low_byte_b0"),
    (0xdc36a, 0xdc464, "generic_state_event_dispatch"),
    (0xdc530, 0xdc584, "actuate_timer_setup"),
    (0xdc584, 0xdc5be, "actuate_timer_callback"),
    (0xdc5be, 0xdc5ee, "set_boost_parameter_indirect"),
    (0xdc5ee, 0xdc71e, "POWER_OFF"),
    (0xdc71e, 0xdc856, "LOW_POWER"),
    (0xdc856, 0xdc9d6, "HIGH_POWER"),
    (0xdc9d6, 0xdc9f4, "low_power_predicate"),
    (0xdc9f4, 0xdca64, "consume_power_events"),
    (0xdca64, 0xdca78, "queue_power_events"),
    (0xdca78, 0xdcaaa, "system_power_event_callback_a"),
    (0xdcaaa, 0xdcadc, "system_power_event_callback_b"),
    (0xdcb5c, 0xdcba8, "pre_download_prepare"),
    (0xdcba8, 0xdcbc0, "enable_dsp"),
    (0xdcbc0, 0xdcc4e, "write_builtin_descriptors"),
    (0xdcc4e, 0xdccc4, "download_builtin"),
    (0xdccc4, 0xdcd54, "write_external_block"),
    (0xdcd54, 0xdcdb8, "download_external"),
    (0xdcdb8, 0xdcdfa, "write_init_registers"),
    (0xdcdfa, 0xdcf90, "initialize_cs40l25"),
    (0xdcf92, 0xdcfd8, "read_dsp_0280000c"),
    (0xdcfd8, 0xdcff2, "trigger_index"),
    (0xdcff2, 0xdd048, "mask_irqs_mailbox_1"),
    (0xdd048, 0xdd086, "mailbox_2_restore_mask"),
    (0xdd086, 0xdd0a0, "set_press_index"),
    (0xdd0a0, 0xdd0ba, "set_release_index"),
    (0xdd0ba, 0xdd148, "read_scaled_02802b08"),
    (0xdd400, 0xdd460, "external_flash_read"),
    (0xdf6a4, 0xdf8f2, "host_command_dispatch"),
    (0xe1aa8, 0xe1ace, "image_block_count"),
    (0xe1ace, 0xe1af4, "image_header_word"),
    (0xe1af4, 0xe1b1e, "image_block_header"),
    (0xe1b1e, 0xe1b94, "image_block_data"),
    (0xe1b94, 0xe1bfc, "locate_image_block"),
    (0xe44b8, 0xe44c2, "boost_object_initialize"),
    (0xe44c2, 0xe450e, "boost_reg4_set_bit7"),
    (0xe450e, 0xe455a, "boost_reg4_clear_bit7"),
    (0xe455a, 0xe4606, "boost_set_parameter"),
    (0xe461c, 0xe4686, "boost_read_regs4_5"),
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def grab(data, offset, size):
    require(offset >= 0 and size >= 0 and offset + size <= len(data), "Out of bounds")
    return data[offset:offset + size]


def u32(data, offset):
    return struct.unpack("<I", grab(data, offset, 4))[0]


def decompress(encoded, limit=0x200000):
    """Bounded transcription of startup codec, including overlapping backrefs."""
    cursor = 0
    output = bytearray()

    def byte():
        nonlocal cursor
        require(cursor < len(encoded), "Truncated compressed token")
        value = encoded[cursor]
        cursor += 1
        return value

    while cursor < len(encoded):
        token = byte()
        literals = token & 3
        if literals == 0:
            literals = byte() + 3
        matches = token >> 4
        if matches == 15:
            matches = byte() + 15
        literals -= 1
        require(len(output) + literals <= limit, "Decompression output limit")
        output.extend(grab(encoded, cursor, literals))
        cursor += literals
        if matches:
            low = byte()
            high = (token >> 2) & 3
            if high == 3:
                high = byte()
            distance = low + (high << 8)
            require(0 < distance <= len(output), "Invalid compressed back-reference")
            require(len(output) + matches + 2 <= limit, "Decompression output limit")
            for _ in range(matches + 2):
                output.append(output[-distance])
    return bytes(output)


def decode_startup(body, variant):
    # Table addresses recovered from each variant's startup dispatcher.
    table = [0xe755c, 0xe915c][variant]
    off = table - BASE
    zero_fn = (table + u32(body, off)) & 0xffffffff
    zero = []
    cursor = off + 4
    while (size := u32(body, cursor)) != 0:
        require(len(zero) < 16, "Unterminated zero table")
        zero.append(dict(address=u32(body, cursor + 4), size=size))
        cursor += 8
    cursor += 4
    segments = []
    for _ in range(2):
        fn = (BASE + cursor + u32(body, cursor)) & 0xffffffff
        header = cursor + 4
        source = header + u32(body, header)
        encoded_size = u32(body, header + 4)
        require(encoded_size & 1 == 0, "Unsupported R9-relative destination")
        destination = u32(body, header + 8)
        encoded = grab(body, source, encoded_size >> 1)
        decoded = decompress(encoded)
        segments.append(dict(table_record=BASE + cursor, decoder=fn & ~1,
                             source_address=BASE + source, destination=destination,
                             encoded=encoded, decoded=decoded))
        cursor = header + 12
    require([s["destination"] for s in segments] == [0x11ddb0, 0x1bb8], "RAM layout mismatch")
    for a in segments:
        alo, ahi = a["destination"], a["destination"] + len(a["decoded"])
        for z in zero:
            require(ahi <= z["address"] or alo >= z["address"] + z["size"], "RAM zero/data overlap")
    return dict(table_address=table, table_end=BASE + cursor, zero_function=zero_fn & ~1,
                zero_ranges=zero, segments=segments)


def asm_lines(path):
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*([0-9a-f]+):.*?\t(.*)", line)
        if m:
            op = m[2].split("@")[0].strip()
            op = re.sub(r"\s+", " ", op)
            records.append((int(m[1], 16), line, op))
    return records


def normalized(op):
    # Relocation-insensitive candidate matching, NOT equivalence verification.
    op = re.sub(r"0x[0-9a-f]+ <[^>]+>", "TARGET", op)
    if "[pc" in op:
        op = re.sub(r"#0x[0-9a-f]+", "PCREL", op)
    if op.startswith("adr"):
        op = re.sub(r"#\d+", "PCREL", op)
    return op


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def touchpad_hid(ram):
    prefix = bytes.fromhex("050d0905a101")
    starts = [m.start() for m in re.finditer(re.escape(prefix), ram)]
    require(len(starts) == 1, "Touchpad HID collection must be unique")
    start = cursor = starts[0]
    depth, entered, items = 0, False, []
    while cursor < len(ram):
        first = ram[cursor]
        require(first != 0xfe, "Unsupported HID long item")
        size = (0, 1, 2, 4)[first & 3]
        payload = grab(ram, cursor + 1, size)
        tag = first & 0xfc
        items.append(dict(ram_address=0x11ddb0 + cursor, prefix=first, value=int.from_bytes(payload, "little")))
        cursor += 1 + size
        if tag == 0xa0:
            depth += 1
            entered = True
        elif tag == 0xc0:
            depth -= 1
            require(depth >= 0, "Unbalanced HID collection")
            if entered and depth == 0:
                descriptor = ram[start:cursor]
                fragment = bytes.fromhex("050e0901a10285d109231500256475089501b102c0")
                require(descriptor.count(fragment) == 1, "Missing intensity feature")
                return dict(start=0x11ddb0 + start, end=0x11ddb0 + cursor,
                            intensity_fragment_address=0x11ddb0 + start + descriptor.index(fragment),
                            intensity_fragment_hex=fragment.hex(), usage_page=14, usage=35,
                            report_id=209, logical_min=0, logical_max=100, report_bits=8,
                            report_count=1, items=items), descriptor
    raise ValueError("Unterminated HID collection")


def analyze(source, output):
    output.mkdir(parents=True, exist_ok=True)
    all_asm = []
    report = {"scope": "Offline evidence, not recovered original source or a flashable image",
              "variants": [], "regions": [], "function_annotations": [], "limitations": [
                  "Full static disassembly includes data interpreted as instructions",
                  "Indirect calls outside the documented context/state tables are not fully resolved",
                  "Variant 1 normalized matches are relocation candidates, not semantic equivalence proof",
                  "Physical timing units, board schematic and on-device behavior are unverified",
                  "Synaptics pressure algorithm is not recovered by this SAM analysis"]}
    for variant in range(2):
        body = (source / f"body_{variant}.bin").read_bytes()
        require(digest(body) == HASHES[variant], "Unsupported SAM body SHA256")
        out = output / f"variant_{variant}"
        out.mkdir(exist_ok=True)
        startup = decode_startup(body, variant)
        v = dict(index=variant, source=str(source / f"body_{variant}.bin"), sha256=digest(body),
                 startup={k: value for k, value in startup.items() if k != "segments"}, ram=[])
        for seg in startup["segments"]:
            stem = f"ram_{seg['destination']:08x}"
            (out / (stem + ".bin")).write_bytes(seg["decoded"])
            (out / (stem + ".compressed.bin")).write_bytes(seg["encoded"])
            v["ram"].append({**{k: value for k, value in seg.items() if k not in ("encoded", "decoded")},
                             "compressed_size": len(seg["encoded"]), "decoded_size": len(seg["decoded"]),
                             "sha256": digest(seg["decoded"])})
        ram = startup["segments"][0]["decoded"]

        def read_ram(addr, size):
            return grab(ram, addr - 0x11ddb0, size)

        def cstr(addr):
            raw = grab(body, addr - BASE, 100).split(b"\0")[0]
            return raw.decode("ascii")

        state = read_ram(0x11e5e4, 33)
        table = u32(state, 21)
        states = []
        for n in range(state[20]):
            sid, name, fn, child = struct.unpack("<HIII", read_ram(table + n * 14, 14))
            states.append(dict(id=sid, name=cstr(name), name_pointer=name,
                               handler=fn & ~1, thumb_pointer=fn, child=child))
        require([s["name"] for s in states] == ["POWER_OFF", "LOW_POWER", "HIGH_POWER"], "State names")
        v["buckboost_state"] = dict(object_address=0x11e5e4, name=cstr(u32(state, 0)),
                                    table_address=table, states=states)
        state = read_ram(0x123444, 33)
        table = u32(state, 21)
        states = []
        for n in range(state[20]):
            sid, name, fn, child = struct.unpack("<HIII", read_ram(table + n * 14, 14))
            states.append(dict(id=sid, name=cstr(name), name_pointer=name,
                               handler=fn & ~1, thumb_pointer=fn, child=child))
        require([s["name"] for s in states] == ["PWR_OFF", "PWR_ON", "INITIALIZE", "NORMAL", "DEEP_SLEEP", "ERROR", "FWUPDATE"], "Lifecycle state names")
        v["touchpad_state"] = dict(object_address=0x123444, name=cstr(u32(state, 0)),
                                   table_address=table, states=states)
        v["boost_vtable"] = list(struct.unpack("<5I", read_ram(0x11e900, 20)))
        v["external_image_context"] = dict(address=0x11e920,
                                           initial_bytes=read_ram(0x11e920, 8).hex())
        hid, descriptor = touchpad_hid(ram)
        (out / "touchpad_hid_collection.bin").write_bytes(descriptor)
        write_json(out / "touchpad_hid_collection.json", hid)
        v["hid_collection"] = {k: value for k, value in hid.items() if k != "items"}
        write_json(out / "recovered_ram_tables.json", v)
        # Preserve every builtin write separately, in loader order; no re-encoding.
        tables = json.loads((source / f"body_{variant}.dsp_tables.json").read_text())
        blocks = out / "dsp_blocks"
        blocks.mkdir(exist_ok=True)
        writes = []
        for group, data in zip(("core", "wave", "wseq"), tables["groups"]):
            for n, row in enumerate(data["rows"]):
                payload = grab(body, row["source_pointer"] - BASE, row["size"])
                require(digest(payload) == row["sha256"], "DSP block mismatch")
                filename = f"{group}_{n:03d}_{row['dsp_address']:08x}"
                (blocks / (filename + ".bin")).write_bytes(payload)
                wire = struct.pack(">I", row["dsp_address"]) + payload
                (blocks / (filename + ".i2c.bin")).write_bytes(wire)
                writes.append(dict(group=group, index=n, dsp_address=row["dsp_address"],
                                   source_pointer=row["source_pointer"], size=len(payload),
                                   file=f"dsp_blocks/{filename}.bin", wire_hex=wire.hex()))
        write_json(out / "builtin_write_sequence.json", writes)
        records = asm_lines(source / f"body_{variant}.annotated.asm")
        all_asm.append(records)
        report["variants"].append(v)

    body = (source / "body_0.bin").read_bytes()
    records = all_asm[0]
    out = output / "variant_0"
    literal_refs, indirect, edges = [], [], []
    for lo, hi, name in REGIONS:
        selected = [r for r in records if lo <= r[0] < hi]
        (out / (name + ".bin")).write_bytes(grab(body, lo - BASE, hi - lo))
        (out / (name + ".asm")).write_text(
            f"; Analyst region {name}, [0x{lo:x}, 0x{hi:x}); contains code AND data.\n" +
            "\n".join(r[1] for r in selected) + "\n", encoding="utf-8")
        report["regions"].append(dict(name=name, variant=0, start=lo, end=hi))
        for addr, line, op in selected:
            m = re.search(r"literal=0x([0-9a-f]+)", line)
            if m:
                value = int(m[1], 16)
                context = grab(body, value - BASE, min(32, BASE + len(body) - value)).hex() if BASE <= value < BASE + len(body) else None
                literal_refs.append(dict(site=addr, value=value, pointed_rom_first32=context, line=line))
            if op.startswith("blx ") or (op.startswith("bx ") and op != "bx lr"):
                indirect.append(dict(site=addr, region=name, instruction=op))
    # Whole-image branch candidates into the selected regions, plus their outgoing calls.
    def region_at(address):
        return next((name for lo, hi, name in REGIONS if lo <= address < hi), None)
    for addr, line, op in records:
        m = re.match(r"(?:bl|b(?:\.w)?) 0x([0-9a-f]+)", op)
        if m:
            target = int(m[1], 16)
            sr, tr = region_at(addr), region_at(target)
            if sr or tr:
                edges.append(dict(site=addr, target=target, source_region=sr, target_region=tr,
                                  candidate_only=True, line=line))
    write_json(out / "literal_references.json", literal_refs)
    write_json(out / "indirect_call_sites.json", indirect)
    write_json(out / "branch_candidates.json", edges)
    # Match function prefixes independently, without a guessed global address delta.
    keys1 = [normalized(r[2]) for r in all_asm[1]]
    indexes = {}
    for i, key in enumerate(keys1):
        indexes.setdefault(key, []).append(i)
    addrs0 = [r[0] for r in records]
    body1 = (source / "body_1.bin").read_bytes()

    def literal_signature(sequence, image):
        values = []
        for _, line, _ in sequence:
            m = re.search(r"literal=0x([0-9a-f]+)", line)
            if m:
                value = int(m[1], 16)
                values.append(grab(image, value - BASE, 8).hex() if BASE <= value <= BASE + len(image) - 8 else value)
        return values

    excerpts = []
    for lo, hi, name in FUNCTIONS:
        a, z = bisect.bisect_left(addrs0, lo), bisect.bisect_left(addrs0, hi)
        expected = [normalized(r[2]) for r in records[a:z]]
        prefix = expected[:24]
        matches = [i for i in indexes.get(prefix[0], []) if keys1[i:i + len(prefix)] == prefix]
        candidates = [all_asm[1][i][0] for i in matches]
        match = dict(name=name, start_0=lo, end_0=hi, variant_1_prefix_candidates=candidates,
                     matched_prefix_instruction_count=len(prefix))
        if len(matches) > 1:
            if name == "boost_object_initialize":
                target = report["variants"][1]["boost_vtable"][0] & ~1
                matches = [i for i in matches if all_asm[1][i][0] == target]
                match["disambiguation"] = "recovered RAM boost vtable entry 0"
            else:
                sig = literal_signature(records[a:z], body)
                matches = [i for i in matches if literal_signature(all_asm[1][i:i + len(expected)], body1) == sig]
                match["disambiguation"] = "equal RAM literal or pointed 8-byte register packet"
        if len(matches) == 1:
            i = matches[0]
            same = keys1[i:i + len(expected)] == expected
            match["whole_normalized_sequence_equal"] = same
            if same:
                start1 = all_asm[1][i][0]
                end1 = all_asm[1][i + len(expected)][0]
                match.update(start_1=start1, end_1=end1)
                excerpts.append(f"\n; {name}; normalized match only, original call targets below.\n" +
                                "\n".join(r[1] for r in all_asm[1][i:i + len(expected)]))
        report["function_annotations"].append(match)
    (output / "variant_1" / "matched_function_candidates.asm").write_text(
        "\n".join(excerpts) + "\n", encoding="utf-8")
    # Device table proven through context construction + low-level address << 1.
    devices = []
    for index in (17, 19):
        address = 0x83d20 + index * 29
        raw = grab(body, address - BASE, 29)
        ptr = u32(raw, 10)
        devices.append(dict(index=index, table_address=address, raw_hex=raw.hex(),
                            name=body[ptr - BASE:].split(b"\0")[0].decode(),
                            seven_bit_address=raw[1], wire_write_address=raw[1] << 1,
                            wire_read_address=(raw[1] << 1) | 1,
                            context_address=0x103e7c + index * 34,
                            lock_wait_raw=u32(raw, 14), transfer_wait_raw=u32(raw, 18),
                            retry_field=raw[22], retry_delay_raw=struct.unpack_from("<H", raw, 23)[0]))
    write_json(out / "i2c_devices.json", devices)
    init = json.loads((source / "body_0.init_tables.json").read_text())
    for table in init:
        address = int(table["table_address"], 16)
        wire = b"".join(bytes.fromhex(row["wire_hex"]) for row in table["writes"])
        require(grab(body, address - BASE, len(wire) + 8) == wire + bytes(8), "Init table mismatch")
        (out / f"init_{address:08x}.i2c.bin").write_bytes(wire)
    write_json(out / "init_register_tables.json", init)
    report["counts"] = dict(regions=len(REGIONS), annotated_functions=len(FUNCTIONS),
                            branch_candidates=len(edges), indirect_sites=len(indirect),
                            normalized_full_matches=sum(bool(f.get("whole_normalized_sequence_equal")) for f in report["function_annotations"]))
    write_json(output / "manifest.json", report)
    files = sorted(p for p in output.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
    (output / "SHA256SUMS").write_text("".join(f"{digest(p.read_bytes())}  {p.relative_to(output).as_posix()}\n" for p in files), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "surface/analysis/sam")
    parser.add_argument("--output", type=Path, default=ROOT / "surface/analysis/sam_control")
    args = parser.parse_args()
    result = analyze(args.source, args.output)
    print(json.dumps(result["counts"], ensure_ascii=False))
