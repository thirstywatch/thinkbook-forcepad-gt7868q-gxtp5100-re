"""步骤3：全镜像 superset 反汇编（所有偶地址），
做"存储目标数据流"分析：对每条 store，回溯 base 寄存器的常量值，
报告任何目标落在 0x40005400-0x40005424 的写操作。
同时报告所有对 I2C1 寄存器的（疑似）访问。
"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

data = seg()
m = md()

# superset 解码：所有偶地址
dec = {}
for o in range(0, len(data) - 1, 2):
    a = SEG_LO + o
    i = insn_at(m, data, a)
    if i is not None:
        dec[a] = i
print("superset 解码指令数 = %d" % len(dec))

ADDRS = sorted(dec.keys())
IDX = {a: k for k, a in enumerate(ADDRS)}

CONST_RE = re.compile(r"^(r\d+),\s*#(0x[0-9a-fA-F]+)$")
STORES = ("str", "strh", "strb", "str.w", "strh.w", "strb.w")

def parse_base_off(ops):
    """从 'rX, [rY, #0xNN]' / 'rX, [rY]' / 'rX, [rY, rZ, lsl #n]' 解析。"""
    mm = re.match(r"(r\d+),\s*\[(r\d+)([^\]]*)\]", ops)
    if not mm:
        return None
    val, base, rest = mm.group(1), mm.group(2), mm.group(3).strip()
    off = None
    kind = "imm"
    if rest == "":
        off = 0
    else:
        r2 = re.match(r",\s*#(-?0x[0-9a-fA-F]+)", rest)
        if r2:
            off = int(r2.group(1), 16)
        else:
            r3 = re.match(r",\s*(r\d+)(,\s*lsl\s*#(\d+))?", rest)
            if r3:
                kind = "reg:" + r3.group(1) + ("<<%s" % r3.group(3) if r3.group(3) else "")
                off = None
            else:
                return None
    return val, base, off, kind

def const_of(reg, addr, depth=0, seen=None):
    """回溯 addr 之前的指令，找 reg 的常量值（movw/movt 或 mov 传递）。"""
    if depth > 4:
        return None
    k = IDX.get(addr)
    if k is None:
        return None
    seen = seen or set()
    n = 0
    while k - n - 1 >= 0 and n < 40:
        j = dec[ADDRS[k - n - 1]]
        ops = j.op_str
        # movw rX, #lo  + movt rX, #hi
        mt = re.match(r"^(r\d+),\s*#(0x[0-9a-fA-F]+)$", ops)
        if mt and j.mnemonic == "movt" and mt.group(1) == reg:
            # 上一条应是 movw
            prev = dec[ADDRS[k - n - 2]] if k - n - 2 >= 0 else None
            if prev is not None and prev.mnemonic == "movw":
                mp = re.match(r"^(r\d+),\s*#(0x[0-9a-fA-F]+)$", prev.op_str)
                if mp and mp.group(1) == reg:
                    return (int(mt.group(2), 16) << 16) | int(mp.group(2), 16)
        if j.mnemonic == "movw" and mt and mt.group(1) == reg:
            return int(mt.group(2), 16)          # 只有 movw（低 16 位）
        if j.mnemonic in ("mov", "mov.w") and mt and mt.group(1) == reg:
            src = mt.group(2)
            if src.startswith("0x"):
                return int(src, 16)
            if re.match(r"^r\d+$", src) and src not in seen:
                r = const_of(src, ADDRS[k - n - 1], depth + 1, seen | {reg})
                if r is not None:
                    return r
        # 如果 reg 被别的指令写过，停止
        if re.match(r"^(%s)\b" % reg, ops) and j.mnemonic not in ("cmp", "str", "ldr", "strh", "strb", "ldrh", "ldrb", "tst", "push", "cbz", "cbnz", "it", "uxtb", "uxth", "sxtb", "sxth"):
            return None
        n += 1
    return None

hits = []
allstores = 0
for a in ADDRS:
    i = dec[a]
    if i.mnemonic not in STORES:
        continue
    p = parse_base_off(i.op_str)
    if not p:
        continue
    val, base, off, kind = p
    allstores += 1
    if "pc" in base or "sp" in base:
        continue
    v = const_of(base, a)
    if v is None:
        continue
    if (0x40005400 <= v <= 0x40005424) or (off is not None and 0x40005400 <= v + off <= 0x40005424):
        tgt = v + (off or 0)
        hits.append((a, i.mnemonic, i.op_str, v, off, kind, val))

print("\n=== 写向 I2C1 寄存器区(0x40005400-0x40005424)的 store（按回溯常量判定）===")
for a, mn, ops, v, off, kind, val in hits:
    print("  0x%08X  %-6s %-28s base=0x%08X off=%s -> 0x%08X  源寄存器=%s" %
          (a, mn, ops, v, off, v + (off or 0), val))
print("  合计 %d；全镜像 store 总数 %d" % (len(hits), allstores))

# 另外：把所有 base 常量 == 0x40005400 的 *读* 也列出来
print("\n=== 读/写 I2C1 基址的全部指令（base 常量回溯为 0x40005400 的 ldr/ldrh/ldrb/str*）===")
rw = []
for a in ADDRS:
    i = dec[a]
    if i.mnemonic not in ("ldr", "ldrh", "ldrb", "ldr.w", "ldrh.w", "ldrb.w") + STORES:
        continue
    p = parse_base_off(i.op_str)
    if not p:
        continue
    val, base, off, kind = p
    if base in ("sp", "pc"):
        continue
    v = const_of(base, a)
    if v is not None and v == 0x40005400:
        rw.append((a, i.mnemonic, i.op_str, off, kind))
for a, mn, ops, off, kind in rw:
    tag = "0x%02X" % off if off is not None else kind
    print("  0x%08X  %-6s %-30s 偏移=%s" % (a, mn, ops, tag))
