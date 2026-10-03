# -*- coding: utf-8 -*-
"""Audit: does the BL-only reachability analysis miss an indirect (function-pointer)
path from the Col04 command dispatcher to the LRA driver?

Target: TF100A plaintext firmware, STM32F1 (Cortex-M3), base 0x08000000.
"""
import collections
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

FW = r"<WORKSPACE>"
BASE = 0x08000000
data = open(FW, "rb").read()
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
md.detail = False
lo, hi = BASE, BASE + len(data)
off = lambda a: a - BASE


def linear_sweep():
    """Capstone stops at the first undecodable byte; restart to sweep the image."""
    out, o = [], 0
    while o < len(data):
        consumed = False
        for insn in md.disasm(data[o:], BASE + o):
            out.append(insn)
            consumed = True
            o = insn.address - BASE + insn.size
        if not consumed:
            o += 2
    return out


insns = linear_sweep()
print("== image ==")
print("bytes decoded into insns:", len(insns), "of", len(data))

bl_edges = collections.defaultdict(set)
blx_sites = []
for insn in insns:
    m, ops = insn.mnemonic, insn.op_str
    if m == "bl":
        try:
            t = int(ops.lstrip("#"), 0)
        except ValueError:
            continue
        if lo <= t < hi:
            bl_edges[insn.address & ~1].add(t & ~1)
    elif m == "blx" and ops.startswith("r"):
        blx_sites.append((insn.address, ops))

print("BL edges:", sum(len(v) for v in bl_edges.values()),
      "from", len(bl_edges), "sites | blx reg sites:", len(blx_sites))
print()

MILESTONES = {
    "play_wrapper_0x8628":    0x08008628,
    "indirect_caller_0x8858": 0x08008858,
    "lra_cfg_TIM3_0x9750":    0x08009750,
    "pwm_cfg_0x8704":         0x08008704,
    "wave_buf_wr_0x88C0":     0x080088C0,
    "clear_arm_0x86B4":       0x080086B4,
    "TIM3_IRQ_0xD628":        0x0800D628,
    "wave_cb_0xD6F4":         0x0800D6F4,
}

HANDLERS = {
    ("A0","0x01"):0x0800937E, ("A0","0x05"):0x0800932A, ("A0","0x0B"):0x08009368,
    ("A0","0x0D"):0x08009378, ("A0","0x0E"):0x080092F4, ("A0","0x11"):0x080092E0,
    ("A0","0x12"):0x08009308, ("A0","0x14"):0x080093BC, ("A0","0x17"):0x08009332,
    ("A0","0x1F"):0x0800934E, ("A0","0x20"):0x080092CE, ("A0","0x24"):0x08009362,
    ("A0","0x26"):0x080093AA, ("A0","0x32"):0x08009396, ("A0","0x33"):0x08009390,
    ("A0","0x35"):0x0800930E,
    ("A1","0x04"):0x0800954A, ("A1","0x07"):0x08009508, ("A1","0x08"):0x080095D8,
    ("A1","0x0A"):0x08009690, ("A1","0x0B"):0x08009674, ("A1","0x0F"):0x08009618,
    ("A1","0x13"):0x08009564, ("A1","0x15"):0x080096C2, ("A1","0x16"):0x080096E0,
    ("A1","0x18"):0x08009586, ("A1","0x1D"):0x080094F0, ("A1","0x23"):0x08009632,
    ("A1","0x28"):0x08009728, ("A1","0x29"):0x080096F8, ("A1","0x2B"):0x080095A2,
    ("A1","0x2C"):0x08009710, ("A1","0x2E"):0x08009532, ("A1","0x32"):0x080096B2,
    ("A1","0x34"):0x08009518, ("A1","0x35"):0x080095FE, ("A1","0x36"):0x0800964E,
}

entries = set()
for v in bl_edges.values():
    entries |= v

def reach(start, maxdepth=40):
    seen, stack, d = set(), [start], 0
    while stack and d < maxdepth:
        nxt = []
        for f in stack:
            if f in seen:
                continue
            seen.add(f)
            nxt.extend(bl_edges.get(f, ()))
        stack, d = nxt, d + 1
    return seen

callers = collections.defaultdict(set)
for src, tgts in bl_edges.items():
    for t in tgts:
        callers[t].add(src)

print("== BL-callers of each milestone ==")
for name, a in MILESTONES.items():
    c = sorted(callers.get(a, ()))
    print(f"  {name:24s} {a:#010x}  n={len(c):3d}  " +
          (", ".join(hex(x) for x in c[:8]) + (" ..." if len(c) > 8 else "") if c else "<none>"))
print()

print("== handler BL-reachability to milestones ==")
hit = collections.defaultdict(list)
for (cls, sub), h in sorted(HANDLERS.items()):
    r = reach(h) | {h}
    for name, a in MILESTONES.items():
        if a in r:
            hit[name].append(f"{cls}-{sub}")
for name in MILESTONES:
    lst = hit.get(name, [])
    print(f"  {name:24s} <- {len(lst):2d} handler(s)  {', '.join(lst[:10]) if lst else '*** NONE ***'}")
print()

reach_all = set()
for h in HANDLERS.values():
    reach_all |= reach(h) | {h}
print("functions BL-reachable from all 39 handlers:", len(reach_all))
print()

print("== THE BLIND SPOT: blx reg sites ==")
def containing(a):
    c = [e for e in entries if e <= a]
    return max(c) if c else None

inreach, total = [], 0
for a, o in blx_sites:
    f = containing(a)
    total += 1
    if f is not None and (f in reach_all or a in reach_all):
        inreach.append((a, o, f))
print(f"  total blx-reg sites in image : {total}")
print(f"  ... inside handler-reachable : {len(inreach)}")
for a, o, f in inreach:
    print(f"    {a:#010x}  blx {o:6s}  in func {f:#010x}")
print()

print("== indirect-call sites that LOAD a pointer then call it ==")
# pattern: ldr rX,[rY,#imm] ; blx rX   (within 4 insns)
for idx, insn in enumerate(insns):
    if insn.mnemonic == "blx" and insn.op_str.startswith("r"):
        reg = insn.op_str
        win = insns[max(0, idx-4):idx]
        loads = [i for i in win if i.mnemonic == "ldr" and i.op_str.startswith(reg + ",")]
        f = containing(insn.address)
        tag = "REACH" if (f and f in reach_all) else "     "
        src = ", ".join(f"{i.mnemonic} {i.op_str}" for i in loads) if loads else "-"
        print(f"  {tag} {insn.address:#010x} blx {reg:5s} | via: {src:34s} | func {f if f is None else hex(f)}")
print()

print("== who materialises 0x0800D6F4 (waveform callback ptr)? ==")
site = []
for insn in insns:
    if insn.mnemonic in ("movw", "movt") and "0xd6f4" in insn.op_str.lower():
        site.append(insn.address)
fns = sorted(set(x for x in (containing(a) for a in site) if x))
print("  movw/movt sites:", ", ".join(hex(x) for x in site) or "<none>")
print("  in functions   :", ", ".join(hex(x) for x in fns) or "<none>")
for f in fns:
    print(f"    func {f:#010x} BL-reached from a handler? {'YES' if f in reach_all else 'NO'}")
print()

print("== raw pointer refs into LRA ctx 0x200040D0..0x20004100 ==")
for t in range(0x200040D0, 0x20004100, 4):
    b = t.to_bytes(4, "little")
    pos, i = [], data.find(b)
    while i >= 0 and len(pos) < 10:
        pos.append(BASE + i); i = data.find(b, i + 1)
    if pos:
        print(f"  {t:#010x}: {len(pos)} ref(s) " + ", ".join(hex(x) for x in pos[:8]))
