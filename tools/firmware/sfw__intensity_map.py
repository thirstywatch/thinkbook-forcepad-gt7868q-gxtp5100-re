#!/usr/bin/env python3
"""Recover the haptic intensity -> waveform index mapping by dataflow.

The project notes state SAM does not write a linear amplitude: it picks a *pair*
of waveform indices (press / release) in five bands inside `setting_to_two_indices`
near 0xD859A. A heuristic scan of `movs` immediates is not good enough -- the
setting==0 arm loads the register once and stores it twice, so "two movs per band"
does not hold. This parses properly instead:

  * locate the function per variant by its distinctive immediate signature
    (cmp #39 / #64 / #89 / #101 with movs #17 #13 #21 #15 #24 #17), because the
    two variants place it at different addresses
  * split into basic blocks at branch targets
  * within each block, track r0 as a known constant through mov/strb and record
    the value stored to [r1] (press) and [r1,#1] (release)
  * attach each block's guard (`cmp`/`bhs` pair) to the block it falls through to

Then the predicate is evaluated over all 256 inputs and the band table is printed.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_OP_REG

HERE = Path(__file__).resolve().parent
SAM = HERE / "out" / "SurfaceSAM_9.101.139"
LOAD_BASE = 0x80000
MD = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
MD.detail = True

# Immediate signature that identifies the function in any variant.
SIGNATURE_CMPS = (0x27, 0x40, 0x59, 0x65)
SIGNATURE_STORE_INDEX = (0x64, 0x11, 0x0D, 0x15, 0x0F, 0x18, 0x24, 0x1D)
WINDOW = 0x200


def imm_of(ins) -> int | None:
    for o in ins.operands:
        if o.type == ARM_OP_IMM:
            return o.imm
    return None


def is_cmp(ins) -> int | None:
    return imm_of(ins) if ins.mnemonic == "cmp" else None


def locate(body: bytes, variant: int) -> int:
    """Find the function start by scanning for the full cmp signature.

    A naive sweep disassembles the whole body at every 2-byte offset, which is
    far too slow. Instead the rare 16-bit `cmp rN, #imm` encodings are located
    directly from their observed bit patterns: 0x2B00 | imm for r3 and
    0x2800 | imm for r0, each followed by a conditional branch. Only those
    candidate sites are disassembled.
    """
    cands = []
    for off in range(0, len(body) - 4, 2):
        hw = struct.unpack_from("<H", body, off)[0]
        if (hw & 0xFF00) not in (0x2B00, 0x2800):
            continue
        imm = hw & 0xFF
        if imm in SIGNATURE_CMPS:
            cands.append((off, imm))

    for off, imm in cands:
        lo = max(0, off - 0x40)
        insns = list(MD.disasm(body[lo:lo + WINDOW], LOAD_BASE + lo))
        cmps = [is_cmp(i) for i in insns]
        present = {c for c in cmps if c is not None}
        if not all(c in present for c in SIGNATURE_CMPS):
            continue
        idx = next((n for n, i in enumerate(insns) if is_cmp(i) == SIGNATURE_CMPS[0]), None)
        if idx is None or idx == 0:
            continue
        # The zero test is a short conditional branch. Capstone prints the
        # 0xD1xx forms as both `b` and `bne` depending on the halfword, so
        # accept any branch mnemonic here and rely on the signature to stay
        # specific -- the four cmp constants are the real discriminator.
        if not insns[idx - 1].mnemonic.startswith("b"):
            continue
        # walk back to the function prologue
        start = idx
        while start > 0 and insns[start - 1].mnemonic not in (
                "push", "push.w", "stmdb", "str", "str.w"):
            start -= 1
        start = max(0, start - 1)
        # the prologue must be a push of lr-containing register list
        if insns[start].mnemonic not in ("push", "push.w", "stmdb"):
            continue
        seen = [imm_of(i) for i in insns[start:start + 0x60]
                if i.mnemonic == "movs" and i.op_str.startswith("r0, #")]
        if all(v in seen for v in SIGNATURE_STORE_INDEX):
            return insns[start].address
    raise ValueError(f"variant {variant}: signature not found")


def analyse_function(body: bytes, start: int) -> dict:
    """Recover arms from the linear store/cmp interleave.

    The function is a flat run of guarded arms, each shaped as

        cmp   rN, #K          <- upper bound (exclusive)
        bhs   next_arm
        movs  r0, #P
        strb  r0, [r1]        <- press
        movs  r0, #R
        strb  r0, [r1, #1]    <- release

    preceded by an unguarded `setting == 0` arm. A basic-block pass is not used
    here because every arm rejoins at one shared exit block, which merges them;
    instead the two `strb` targets disambiguate the arms unambiguously, and each
    arm is attributed to the closest preceding `cmp`.
    """
    span = 0x100
    off = start - LOAD_BASE
    insns = list(MD.disasm(body[off:off + span], start))

    r0 = None
    guard = None
    armed = False
    zero_arm = None
    arms = []
    stores = []
    pending = None

    for ins in insns:
        m, ops = ins.mnemonic, ins.op_str

        c = is_cmp(ins)
        if c is not None:
            guard = c
            continue

        if m == "movs" and ops.startswith("r0, #"):
            r0 = imm_of(ins)
        elif m == "mov" and ops.startswith("r0, #"):
            r0 = imm_of(ins) & 0xFFFFFFFF
        elif m in ("movw", "movt", "ldr"):
            r0 = None
        elif m == "push" or m == "push.w":
            r0 = None

        if m == "strb" and "[r1]" in ops and ops.endswith("]"):
            pending = dict(press=r0, lt=guard, press_at=f"0x{ins.address:08X}")
            stores.append(dict(address=f"0x{ins.address:08X}", text=f"{m} {ops}",
                               slot="press",
                               value=None if r0 is None else f"0x{r0:02X}"))
        elif m == "strb" and "[r1, #1]" in ops:
            stores.append(dict(address=f"0x{ins.address:08X}", text=f"{m} {ops}",
                               slot="release",
                               value=None if r0 is None else f"0x{r0:02X}"))
            if pending is not None and r0 is not None and pending["press"] is not None:
                arm = dict(lt=pending["lt"], press=pending["press"], release=r0,
                           at=pending["press_at"])
                if arm["lt"] is None:
                    zero_arm = arm
                else:
                    arms.append(arm)
            pending = None

    return dict(start=f"0x{start:08X}", zero_arm=zero_arm, bands=arms,
                stores=stores, decoded=len(insns))


def status_constant(body: bytes, after: int) -> int | None:
    """The `ldr rX, [pc, #imm]` status constant loaded when out of range."""
    off = after - LOAD_BASE
    for ins in MD.disasm(body[off:off + 0x40], after):
        if ins.mnemonic == "ldr" and "[pc," in ins.op_str:
            disp = ins.operands[-1].mem.disp
            pool = ((ins.address + 4) & ~3) + disp
            return struct.unpack_from("<I", body, pool - LOAD_BASE)[0]
    return None


def build_table(zero_arm, bands, keep) -> list[dict]:
    """Evaluate the recovered predicate for all 256 possible setting values.

    Above the top band the function loads a status constant (0x8300001F) and
    returns it without touching the index pair, i.e. "keep whatever was already
    programmed". That constant is a status code, not a waveform index, so it is
    reported as None here and kept separately.
    """
    rows = []
    for s in range(256):
        if s == 0 and zero_arm:
            rows.append(dict(setting=0, press=zero_arm["press"],
                             release=zero_arm["release"], branch="zero_special"))
            continue
        hit = next((b for b in bands if s < b["lt"]), None)
        if hit:
            rows.append(dict(setting=s, press=hit["press"],
                             release=hit["release"],
                             branch=f"<{hit['lt']}"))
        else:
            rows.append(dict(setting=s, press=None, release=None,
                             branch="out_of_range_keep_previous"))
    return rows


def main():
    report = {}
    for variant in (0, 1):
        body = (SAM / f"body_{variant}.bin").read_bytes()
        try:
            start = locate(body, variant)
        except ValueError as exc:
            print(f"=== variant {variant}: {exc}")
            continue
        info = analyse_function(body, start)
        keep = status_constant(body, start + 0x40)
        rows = build_table(info["zero_arm"], info["bands"], keep)

        groups = {}
        for r in rows:
            groups.setdefault((r["press"], r["release"]), []).append(r["setting"])

        print(f"=== variant {variant}")
        print(f"  function located at {info['start']}  ({info['decoded']} insns decoded)")
        print(f"  zero arm: {info['zero_arm']}")
        print(f"  guarded arms: {[(b['lt'], b['press'], b['release']) for b in info['bands']]}")
        print(f"  out-of-range status constant: {keep and hex(keep)}")
        print("  stores that write the two indices:")
        for s in info["stores"]:
            print(f"      {s['address']}  {s['text']:<22} value={s['value']}")
        print("  recovered mapping over 0..255:")
        for (p, r), vals in sorted(groups.items(), key=lambda kv: min(kv[1])):
            lo, hi = min(vals), max(vals)
            span = str(lo) if lo == hi else f"{lo}..{hi}"
            print(f"      {span:>9}  press={str(p):<4} release={str(r):<4} ({len(vals)} values)")
        print()

        report[f"variant_{variant}"] = dict(
            function=info["start"], zero_arm=info["zero_arm"],
            bands=[dict(lt=b["lt"], press=b["press"], release=b["release"])
                   for b in info["bands"]],
            out_of_range_status=(f"0x{keep:08X}" if keep is not None else None),
            stores=info["stores"], table=rows,
            summary=[dict(lo=min(v), hi=max(v), press=p, release=r, count=len(v))
                     for (p, r), v in sorted(groups.items(), key=lambda kv: min(kv[1]))])

    (SAM / "intensity_map.json").write_text(json.dumps(report, indent=1),
                                             encoding="utf-8")


if __name__ == "__main__":
    main()
