#!/usr/bin/env python3
"""Recursive-descent Thumb disassembly of the SAM bodies.

A linear sweep is useless here: the SAM bodies interleave code and data, so a
sweep halts at the first data word it meets (0x80174 for variant 0) and yields a
few hundred instructions instead of tens of thousands.

This walks the control flow instead: from the vector table, follow branches,
literal-pool loads and call targets, and only disassemble where control can
actually reach. Everything reached this way is genuinely code; the listing
records which entry point proved each region reachable.

    entry points: the 16 core vectors + the first 32 IRQs
"""
from __future__ import annotations

import hashlib
import json
import struct
from collections import deque
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_OP_REG

HERE = Path(__file__).resolve().parent
SAM = HERE / "out" / "SurfaceSAM_9.101.139"
LOAD_BASE = 0x80000
MD = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
MD.detail = True

VECTOR_NAMES = ["SP", "Reset", "NMI", "HardFault", "MemManage", "BusFault",
                "UsageFault", "Rsv7", "Rsv8", "Rsv9", "Rsv10", "SVCall",
                "DebugMon", "Rsv13", "PendSV", "SysTick"]


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def vectors(body: bytes) -> list[dict]:
    out = []
    for k in range(16):
        v = struct.unpack_from("<I", body, k * 4)[0]
        if k == 0:
            out.append(dict(index=k, name="initial_SP", value=f"0x{v:08X}", thumb=None))
        else:
            out.append(dict(index=k, name=VECTOR_NAMES[k], value=f"0x{v & ~1:08X}",
                            raw=f"0x{v:08X}", thumb=bool(v & 1)))
    for n in range(32):
        off = 64 + 4 * n
        if off + 4 > len(body):
            break
        v = struct.unpack_from("<I", body, off)[0]
        out.append(dict(index=16 + n, name=f"IRQ{n}", value=f"0x{v & ~1:08X}",
                        raw=f"0x{v:08X}", thumb=bool(v & 1)))
    return out


def branch_targets(ins) -> list[int]:
    """Runtime addresses this instruction transfers control to."""
    out = []
    m = ins.mnemonic
    if m.startswith("b") and m not in ("bic", "bfi", "bfc", "bicas", "bkpt"):
        try:
            imm = ins.operands[0].imm
        except (IndexError, AttributeError):
            imm = None
        if imm is not None:
            # capstone reports branch immediates as absolute for Thumb
            out.append(imm & ~1 if m not in ("bl", "blx") else imm & ~1)
    elif m in ("pop", "ldm", "ldmia", "ldr", "mov", "movw", "movt") and "pc" in ins.op_str:
        # pc-relative load: the loaded word may be a code pointer
        out.append(("pool", ins))
    return out


def disassemble(body: bytes, variant: int) -> dict:
    vecs = vectors(body)
    entries = []
    for v in vecs:
        if v["name"] == "initial_SP" or v.get("thumb") is None:
            continue
        if v.get("thumb"):
            entries.append(int(v["value"], 16))
    entries = sorted(set(entries))

    seen: set[int] = set()
    origin: dict[int, str] = {}
    queue = deque()
    for e in entries:
        if e not in seen:
            seen.add(e)
            origin[e] = "vector"
            queue.append(e)

    insns: dict[int, object] = {}
    unresolved_pool = []

    while queue:
        addr = queue.popleft()
        off = addr - LOAD_BASE
        if not (0 <= off < len(body) - 1):
            continue
        # linear from here until we leave the function or hit invalid bytes
        cur = off
        while 0 <= cur < len(body) - 1:
            runtime = LOAD_BASE + cur
            if runtime in insns:
                break
            chunk = body[cur:cur + 4]
            decoded = list(MD.disasm(bytes(chunk), runtime, count=1))
            if not decoded:
                break
            ins = decoded[0]
            # a Thumb instruction is 2 or 4 bytes; 4-byte ones have bit0 of the
            # first halfword clear in the *next* halfword
            size = 4 if (cur + 2 < len(body) and
                         (struct.unpack_from("<H", body, cur + 2)[0] & 0xF800) in
                         (0xE800, 0xF000, 0xF800)) else 2
            insns[runtime] = ins
            origin.setdefault(runtime, "flow")

            # follow branches
            for t in branch_targets(ins):
                if isinstance(t, tuple):
                    unresolved_pool.append((runtime, t[1]))
                    continue
                if t not in seen and (LOAD_BASE <= t < LOAD_BASE + len(body)):
                    seen.add(t)
                    queue.append(t)

            if m_is_return(ins.mnemonic) or ins.mnemonic in ("b", "b.w") and \
                    not ins.op_str.startswith("#"):
                # unconditional outbound branch ends this linear run
                if ins.mnemonic in ("b", "b.w"):
                    break
            if ins.mnemonic == "pop" and "pc" in ins.op_str:
                break
            cur += size
            if size == 2 and ins.mnemonic in ("b", "b.w", "bne", "bne.w",
                                              "beq", "beq.w", "bgt", "bgt.w",
                                              "blt", "blt.w", "bge", "bge.w",
                                              "bhi", "bhi.w", "bls", "bls.w",
                                              "bcc", "bcc.w", "bcs", "bcs.w",
                                              "ble", "ble.w", "bvc", "bvc.w",
                                              "bvs", "bvs.w"):
                pass  # conditional branch: fallthrough is real code too

    # Second pass: resolve PC-relative literal loads into data addresses.
    data_refs = []
    for runtime, ins in sorted(insns.items()):
        if "[pc," not in ins.op_str:
            continue
        try:
            disp = ins.operands[-1].mem.disp
        except (IndexError, AttributeError):
            continue
        pool = ((runtime + 4) & ~3) + disp
        off = pool - LOAD_BASE
        if 0 <= off + 4 <= len(body):
            val = struct.unpack_from("<I", body, off)[0]
            data_refs.append(dict(code=f"0x{runtime:08X}",
                                  text=f"{ins.mnemonic} {ins.op_str}",
                                  pool=f"0x{pool:08X}",
                                  value=f"0x{val:08X}",
                                  points_into_code=LOAD_BASE <= val < LOAD_BASE + len(body)))

    return dict(vectors=vecs, entry_count=len(entries),
                reachable=len(insns), origin=origin, data_refs=data_refs,
                insns=insns, body=body)


def m_is_return(mn: str) -> bool:
    return mn.startswith("bx") and False


def main():
    for variant in (0, 1):
        body = (SAM / f"body_{variant}.bin").read_bytes()
        r = disassemble(body, variant)
        insns = r["insns"]
        with (SAM / f"disasm_{variant}.txt").open("w", encoding="utf-8") as f:
            f.write(f"; SAM variant {variant} recursive-descent Thumb disassembly\n")
            f.write(f"; body {len(body):,} bytes  load base 0x{LOAD_BASE:X}  "
                    f"sha256 {sha(body)}\n")
            f.write(f"; vectors {r['entry_count']}  reachable instructions {len(insns)}\n\n")
            for addr in sorted(insns):
                ins = insns[addr]
                f.write(f"{addr:08x}  {ins.bytes.hex():<10} {ins.mnemonic:<9} "
                        f"{ins.op_str}\n")
        (SAM / f"flow_{variant}.json").write_text(json.dumps(
            dict(variant=variant, body_sha256=sha(body), body_bytes=len(body),
                 load_base=LOAD_BASE, vectors=r["vectors"],
                 entry_count=r["entry_count"], reachable=len(insns),
                 origin=r["origin"], data_refs=r["data_refs"]), indent=1),
            encoding="utf-8")
        print(f"=== variant {variant}")
        print(f"  body {len(body):,} B  sha {sha(body)[:16]}")
        print(f"  vector entries {r['entry_count']}  reachable insns {len(insns):,}")
        vc = sum(1 for v in r["vectors"] if v.get("thumb"))
        print(f"  thumb vectors {vc}/{len(r['vectors'])}")
        print(f"  pc-relative data refs {len(r['data_refs'])}")
        for v in r["vectors"][:16]:
            print(f"    [{v['index']:2}] {v['name']:<10} {v['value']}"
                  f"{' T' if v.get('thumb') else ''}")
        print()


if __name__ == "__main__":
    main()
