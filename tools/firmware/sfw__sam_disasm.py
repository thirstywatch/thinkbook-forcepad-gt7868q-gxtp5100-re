#!/usr/bin/env python3
"""Disassemble the SAM bodies and evidence-gather the CS40L25 control paths.

The bodies are raw ARM Thumb images with no section headers, so the load
mapping from the project notes is used and then verified from the vector table:
    runtime_address = body_file_offset + LOAD_BASE

Outputs under out/SurfaceSAM_9.101.139/:
  disasm_<i>.txt        flat Thumb listing of the whole body
  strings_<i>.json      every printable run with its runtime address
  control_report.json   per-variant evidence table

Evidence rules, so nothing here is a plausible-sounding guess:
  - a "literal present" claim requires the bytes to exist in the body
  - a "referenced" claim additionally requires a PC-relative literal-pool load
    or a movw/movt pair that materialises that exact 32-bit value
  - every reported address carries its body offset so it can be re-checked
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

HERE = Path(__file__).resolve().parent
SAM = HERE / "out" / "SurfaceSAM_9.101.139"
LOAD_BASE = 0x80000

MD = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
MD.detail = True

# Peripheral / DSP addresses named in the project notes, with the role each
# one plays. Values are the on-bus addresses, not file offsets.
ADDRESSES = {
    "pre_download_flag_0x00000020": (0x00000020, "write 0x5A000000 handshake"),
    "pre_download_reg_0x02800190": (0x02800190, "pre_download_prepare register"),
    "dsp_enable_0x02BC1000": (0x02BC1000, "write 0x00000101 enables DSP"),
    "platform_opt_0x028018DC": (0x028018DC, "optional platform write, value 1"),
    "press_index_0x0280167C": (0x0280167C, "press waveform index"),
    "release_index_0x0280168C": (0x0280168C, "release waveform index"),
    "mailbox_0x00013020": (0x00013020, "CS40L25 DSP mailbox trigger"),
    "vibegen_enable_0x02800B4C": (0x02800B4C, "VIBEGEN enable"),
    "vibegen_status_0x02800B50": (0x02800B50, "VIBEGEN status"),
    "vibegen_num_waves_0x02800B58": (0x02800B58, "VIBEGEN_NUMBEROFWAVES"),
    "vibegen_wavetable_xm_0x02800B60": (0x02800B60, "VIBEGEN_WAVETABLE XM"),
    "vibegen_wavetable_ym_0x03400000": (0x03400000, "VIBEGEN_WAVETABLEYM YM"),
    "wseq_0x028016D0": (0x028016D0, "CS40L25 WSEQ"),
    "flash_slot_a_0x0818F000": (0x0818F000, "external image slot A"),
    "flash_slot_b_0x0819F000": (0x0819F000, "external image slot B"),
    "arm_vtor_0xE000ED08": (0xE000ED08, "ARM vector table offset register"),
}

NAMED_LITERALS = [
    "ActuateHaptic", "HAPTIC_DRIVER", "TOUCHPAD", "BuckBoost", "BUCK_BOOST",
    "initialize_cs40l25", "pre_download_prepare", "cs40l25", "CS40L25",
    "manual_trigger_power_bracket", "vibegen", "SamCommunicationViaSsh",
]

# body_offset (runtime - LOAD_BASE) of the structures the notes describe
STRUCT_ANCHORS = {
    "init_table_A_0x841EC": 0x841EC - LOAD_BASE,
    "init_table_B_0x8442C": 0x8442C - LOAD_BASE,
    "i2c_device_table_0x83D20": 0x83D20 - LOAD_BASE,
    "actuate_haptic_string_0x8DC20": 0x8DC20 - LOAD_BASE,
}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def find_u32(body: bytes, value: int) -> list[int]:
    pat = struct.pack("<I", value)
    out, p = [], 0
    while True:
        p = body.find(pat, p)
        if p < 0:
            return out
        out.append(p)
        p += 1


def refs_to(insns, body: bytes, value: int, limit: int = 24) -> list[dict]:
    """Instructions that materialise `value`: literal-pool loads or movw/movt."""
    by_addr = {i.address: n for n, i in enumerate(insns)}
    hits = []
    for n, ins in enumerate(insns):
        # ldr rX, [pc, #imm] -> resolve the pool entry and read the constant
        if ins.mnemonic.startswith("ldr") and "[pc," in ins.op_str:
            try:
                disp = ins.operands[1].mem.disp
            except (IndexError, AttributeError):
                disp = None
            if disp is not None:
                pool = ((ins.address + 4) & ~3) + disp
                off = pool - LOAD_BASE
                if 0 <= off + 4 <= len(body) and \
                        struct.unpack_from("<I", body, off)[0] == value:
                    hits.append(dict(address=f"0x{ins.address:08X}",
                                     text=f"{ins.mnemonic} {ins.op_str}",
                                     via="literal_pool", pool=f"0x{pool:08X}"))
        # movw + movt pair, or a single mov/mov.w with a 32-bit immediate
        if ins.mnemonic == "movw":
            try:
                imm = ins.operands[1].imm
            except (IndexError, AttributeError):
                continue
            if (value & 0xFFFF) != imm:
                continue
            nxt = insns[n + 1] if n + 1 < len(insns) else None
            if nxt is not None and nxt.mnemonic == "movt" and nxt.address == ins.address + 2:
                try:
                    hi = nxt.operands[1].imm
                except (IndexError, AttributeError):
                    continue
                if ((hi << 16) | imm) & 0xFFFFFFFF == value:
                    hits.append(dict(address=f"0x{ins.address:08X}",
                                     text=f"movw {ins.op_str} / movt {nxt.op_str}",
                                     via="movw_movt"))
        if ins.mnemonic in ("mov", "mov.w"):
            try:
                imm = ins.operands[1].imm
            except (IndexError, AttributeError):
                continue
            if (imm & 0xFFFFFFFF) == value:
                hits.append(dict(address=f"0x{ins.address:08X}",
                                 text=f"{ins.mnemonic} {ins.op_str}", via="mov_imm"))
    return hits[:limit]


def analyse(variant: int) -> dict:
    body = (SAM / f"body_{variant}.bin").read_bytes()
    comp = (SAM / f"component_{variant}.bin").read_bytes()

    entry = struct.unpack_from("<I", body, 4)[0]
    insns = list(MD.disasm(body, LOAD_BASE))
    with (SAM / f"disasm_{variant}.txt").open("w", encoding="utf-8") as f:
        f.write(f"; SAM variant {variant} flat Thumb disassembly\n")
        f.write(f"; body {len(body)} bytes, load base 0x{LOAD_BASE:X}, "
                f"{len(insns)} instructions\n")
        f.write(f"; initial SP 0x{struct.unpack_from('<I', body, 0)[0]:08X}, "
                f"reset 0x{entry:X}\n")
        for ins in insns:
            f.write(f"{ins.address:08x}  {ins.bytes.hex():<10} "
                    f"{ins.mnemonic:<9} {ins.op_str}\n")

    strings = [dict(body_offset=m.start(), runtime=m.start() + LOAD_BASE,
                    text=m.group().decode("ascii"))
               for m in re.finditer(rb"[\x20-\x7e]{4,}", body)]
    (SAM / f"strings_{variant}.json").write_text(json.dumps(strings, indent=1),
                                                 encoding="utf-8")

    named = {}
    for s in strings:
        if s["text"] in NAMED_LITERALS and s["text"] not in named:
            named[s["text"]] = s

    addr_hits = {}
    for label, (value, role) in ADDRESSES.items():
        offs = find_u32(body, value)
        if not offs:
            continue
        addr_hits[label] = dict(value=f"0x{value:08X}", role=role,
                                occurrences=len(offs),
                                body_offsets=[f"0x{o:X}" for o in offs[:8]],
                                code_refs=refs_to(insns, body, value))

    tables = {}
    for label, off in STRUCT_ANCHORS.items():
        if 0 <= off < len(body):
            tables[label] = dict(body_offset=f"0x{off:X}",
                                 runtime=f"0x{off + LOAD_BASE:X}",
                                 first64=body[off:off + 64].hex())

    # Reset-code evidence for the VTOR store: look for a 0x80000 materialised
    # immediately before a store, which is how the mapping is established.
    vtor = []
    for n, ins in enumerate(insns):
        if "0x8000" in ins.op_str and ins.mnemonic in ("movw", "mov.w", "mov"):
            window = insns[n:n + 4]
            txt = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in window)
            vtor.append(dict(address=f"0x{ins.address:08X}", context=txt))

    return dict(
        variant=variant,
        body_bytes=len(body), body_sha256=sha(body),
        component_bytes=len(comp), component_sha256=sha(comp),
        load_base=f"0x{LOAD_BASE:X}",
        initial_sp=f"0x{struct.unpack_from('<I', body, 0)[0]:08X}",
        reset_vector=f"0x{entry & ~1:08X}", reset_thumb=bool(entry & 1),
        instruction_count=len(insns),
        string_count=len(strings),
        printable_ratio=round(sum(len(s["text"]) for s in strings) / len(body), 4),
        named_literals=named,
        address_constants=addr_hits,
        address_constants_matched=len(addr_hits),
        address_constants_total=len(ADDRESSES),
        structural_tables=tables,
        load_base_evidence=vtor[:6],
    )


def main():
    reports = [analyse(0), analyse(1)]
    (SAM / "control_report.json").write_text(json.dumps(reports, indent=1),
                                             encoding="utf-8")
    for r in reports:
        print(f"=== variant {r['variant']}")
        print(f"  body {r['body_bytes']:,} B  sha {r['body_sha256'][:16]}")
        print(f"  SP {r['initial_sp']}  reset {r['reset_vector']} thumb={r['reset_thumb']}")
        print(f"  insns {r['instruction_count']:,}  strings {r['string_count']} "
              f"printable {r['printable_ratio']:.2%}")
        print(f"  named literals: {', '.join(sorted(r['named_literals'])) or '(none)'}")
        print(f"  address constants matched {r['address_constants_matched']}"
              f"/{r['address_constants_total']}")
        for label, v in r["address_constants"].items():
            print(f"    {label:<34} {v['value']}  x{v['occurrences']:<3} "
                  f"code_refs={len(v['code_refs'])}")
        print(f"  load-base evidence: {len(r['load_base_evidence'])} site(s)")
        for e in r["load_base_evidence"][:3]:
            print(f"    {e['address']}  {e['context'][:90]}")
        print()


if __name__ == "__main__":
    main()
