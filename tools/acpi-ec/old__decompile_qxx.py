# -*- coding: utf-8 -*-
"""Minimal AML disassembler: decompile every _Qxx method of the dumped DSDT to pseudo-ASL.

Fixes vs v1:
  * arg-count table built across ALL dumped tables (not just DSDT) -> fewer desyncs
  * Store() operand order (AML is StoreOp Source Dest)
  * method end clamped to the next MethodOp so a parse can never bleed into the neighbour
  * 0x5B 0x12 handled as a 2-operand extended op
"""
import os, re, glob

DIR = r"<WORKSPACE>"
DSDT = os.path.join(DIR, "DSDT_LENOVO_CB-01____00000001.bin")
D = open(DSDT, "rb").read()
HDR = 36
NL = len(D)
NC = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


def pkg_in(d, i):
    """读 AML PkgLength（i 指向首字节）。返回 (值, 总占用字节数)。

    ★ 编码（ACPI 规范 20.2.4）：lead 高 2 位 n = 后续字节数；低 4 位是最低 nibble；
      之后 n 个字节依次提供更高的位：b[i+1] → bits 4-11，b[i+2] → bits 12-19 …
      ⇒ PkgLength = (lead & 0x0F) | (b[i+1] << 4) | (b[i+2] << 12) | (b[i+3] << 20)
      ⇒ 总占用字节数 = 1 + n。

    ★ 2026-09-29 修正：原实现用 `d[i+k] << (8*k)`（第一个后续字节放到 bits 8-15），
      与规范不符。DSDT 实测（421 个 DeviceOp）：旧式让 TPAD(`5B 82 48 3D`) 算出
      0x3D48 → 越界 8 处；新式算出 0x3D8，包尾 0x070804 紧随 `Scope(_SB.PC00)`，
      全表 420/421 在界内且包尾首字节全是合法 AML 操作符。
    """
    if i >= len(d):
        return None, 0
    lead = d[i]; n = lead >> 6
    if n == 0:
        return lead & 0x3F, 1
    v = lead & 0x0F
    for k in range(n):
        if i + 1 + k >= len(d):
            return None, 0
        v |= d[i + 1 + k] << (4 + 8 * k)
    return v, 1 + n


def nameseg_in(d, i):
    if i + 4 > len(d):
        return None, i
    if d[i] == 0x00:
        return None, i + 1
    if d[i] == 0x2E:
        a, b = d[i + 1:i + 5], d[i + 5:i + 9]
        if all(c in NC for c in a) and all(c in NC for c in b):
            return a.decode() + "." + b.decode(), i + 9
        return None, i
    if d[i] == 0x2F:
        n = d[i + 1]
        segs = [d[i + 2 + 4 * k:i + 6 + 4 * k] for k in range(n)]
        if n and all(all(c in NC for c in s) for s in segs):
            return ".".join(s.decode() for s in segs), i + 2 + 4 * n
        return None, i
    if d[i] in NC and all(c in NC for c in d[i:i + 4]):
        return d[i:i + 4].decode(), i + 4
    return None, i


# ---------- pass 1: arg counts across every table ----------
ARGS = {"_STA": 0, "_INI": 0, "_LID": 0, "_PSR": 0, "_BQC": 0, "_TMP": 0, "_BST": 0,
        "_BIF": 0, "_EC": 0, "_HID": 0, "_UID": 0, "_DSM": 4, "_BCM": 1, "_ON": 0, "_OFF": 0}
method_starts = []


def scan(data):
    i = 0
    while True:
        j = data.find(b"\x14", i)
        if j < 0:
            return
        i = j + 1
        v, n = pkg_in(data, j + 1)
        if v is None or v < 4 or j + 1 + n + 5 > len(data):
            continue
        k = j + 1 + n
        nm, k2 = nameseg_in(data, k)
        if nm is None or k2 >= len(data):
            continue
        if data[k2] <= 7:
            ARGS[nm.split(".")[-1]] = data[k2]
            method_starts.append(j)


for p in sorted(glob.glob(os.path.join(DIR, "*.bin"))):
    scan(open(p, "rb").read())

NEXT_METHOD = {}


def next_after(x, lim):
    c = [s for s in method_starts if s > x]
    return min(c) if c else lim


# ---------- opcode rendering ----------
def is_ns_at(i):
    if i + 4 > NL:
        return False
    if D[i] in (0x2E, 0x2F):
        return True
    return D[i] in NC and all(c in NC for c in D[i:i + 4])


UN = {0x75: "Increment", 0x76: "Decrement", 0x87: "SizeOf", 0x8E: "ObjectType",
      0x71: "RefOf", 0x83: "DerefOf", 0x92: "LNot"}
BIN3 = {0x72: "Add", 0x74: "Subtract", 0x77: "Multiply", 0x79: "ShiftLeft", 0x7A: "ShiftRight",
        0x7B: "And", 0x7C: "Nand", 0x7D: "Or", 0x7E: "Nor", 0x7F: "Xor", 0x73: "Concat",
        0x84: "ConcatRes", 0x85: "Mod", 0x88: "Index"}
BIN2 = {0x80: "Not", 0x81: "FindSetLeftBit", 0x82: "FindSetRightBit", 0x90: "LAnd",
        0x91: "LOr", 0x93: "LEqual", 0x94: "LGreater", 0x95: "LLess",
        0x97: "ToBuffer", 0x98: "ToDecimalString", 0x9C: "ToInteger", 0x9D: "ToString",
        0x9E: "CopyObject"}


def const(i):
    op = D[i]
    if op == 0x00: return "Zero", i + 1
    if op == 0x01: return "One", i + 1
    if op == 0xFF: return "Ones", i + 1
    if op == 0x0A: return str(D[i + 1]), i + 2
    if op == 0x0B: return "0x%X" % int.from_bytes(D[i + 1:i + 3], "little"), i + 3
    if op == 0x0C: return "0x%X" % int.from_bytes(D[i + 1:i + 5], "little"), i + 5
    if op == 0x0E: return "0x%X" % int.from_bytes(D[i + 1:i + 9], "little"), i + 9
    return None, i


def parse_term(i, depth=0, limit=NL):
    if depth > 16 or i >= limit:
        return "?", min(i + 1, limit)
    b = D[i]
    if 0x60 <= b <= 0x67:
        return "Local%d" % (b - 0x60), i + 1
    if 0x68 <= b <= 0x6E:
        return "Arg%d" % (b - 0x68), i + 1
    if b in (0x5C, 0x5E, 0x2E, 0x2F) or b in NC:
        pre = ""
        j = i
        while j < limit and D[j] in (0x5C, 0x5E):
            pre += "\\" if D[j] == 0x5C else "^"
            j += 1
        nm, j = nameseg_in(D, j)
        if nm is None:
            return "?%02X" % b, i + 1
        full = pre + nm
        nargs = ARGS.get(nm.split(".")[-1], 0)
        if nargs:
            args = []
            for _ in range(nargs):
                t, j = parse_term(j, depth + 1, limit)
                args.append(t)
            return "%s(%s)" % (full, ", ".join(args)), j
        return full, j
    c, j = const(i)
    if c is not None:
        return c, j
    if b == 0x0D:
        j = D.index(0, i + 1)
        return '"%s"' % D[i + 1:j].decode("ascii", "replace"), j + 1
    if b == 0x11:
        v, n = pkg_in(D, i + 1)
        sz, k = parse_term(i + 1 + n, depth + 1, limit)
        end = min(i + 1 + n + v, limit)
        return "Buffer(%s){...}" % sz, max(end, k)
    if b in (0x12, 0x13):
        v, n = pkg_in(D, i + 1)
        p = i + 1 + n
        if b == 0x12:
            cnt = D[p]; p += 1
        else:
            cnt, p = parse_term(p, depth + 1, limit)
        end = min(i + 1 + n + v, limit)
        elems = []
        while p < end and len(elems) < 10:
            t, p = parse_term(p, depth + 1, limit)
            elems.append(t)
        return "Package(%s){%s}" % (cnt, ", ".join(elems)), end
    if b == 0x5B:
        s = D[i + 1]
        if s == 0x31: return "Debug", i + 2
        if s == 0x30: return "Revision", i + 2
        if s == 0x33: return "Timer", i + 2
        if s == 0x12:
            a, j = parse_term(i + 2, depth + 1, limit)
            t, j = parse_term(j, depth + 1, limit)
            return "CondRefOf(%s, %s)" % (a, t), j
        if s in (0x21, 0x22, 0x26, 0x27, 0x24):
            a, j = parse_term(i + 2, depth + 1, limit)
            nm = {0x21: "Stall", 0x22: "Sleep", 0x26: "Reset", 0x27: "Release", 0x24: "Signal"}[s]
            return "%s(%s)" % (nm, a), j
        if s in (0x20, 0x23, 0x25, 0x2A):
            a, j = parse_term(i + 2, depth + 1, limit)
            b2, j = parse_term(j, depth + 1, limit)
            nm = {0x20: "Load", 0x23: "Acquire", 0x25: "Wait", 0x2A: "Unload"}[s]
            return "%s(%s, %s)" % (nm, a, b2), j
        if s == 0x32:
            return "Fatal", i + 4
        return "Ext5B%02X" % s, i + 2
    if b in UN:
        t, j = parse_term(i + 1, depth + 1, limit)
        return "%s(%s)" % (UN[b], t), j
    if b in BIN2:
        a, j = parse_term(i + 1, depth + 1, limit)
        c2, j = parse_term(j, depth + 1, limit)
        return "%s(%s, %s)" % (BIN2[b], a, c2), j
    if b in BIN3:
        a, j = parse_term(i + 1, depth + 1, limit)
        c2, j = parse_term(j, depth + 1, limit)
        d, j = parse_term(j, depth + 1, limit)
        return "%s(%s, %s, %s)" % (BIN3[b], a, c2, d), j
    if b == 0x70:
        a, j = parse_term(i + 1, depth + 1, limit)
        c2, j = parse_term(j, depth + 1, limit)
        return "Store(%s, %s)" % (a, c2), j
    if b == 0x86:
        a, j = parse_term(i + 1, depth + 1, limit)
        c2, j = parse_term(j, depth + 1, limit)
        return "Notify(%s, %s)" % (a, c2), j
    if b == 0x78:
        a, j = parse_term(i + 1, depth + 1, limit)
        c2, j = parse_term(j, depth + 1, limit)
        d, j = parse_term(j, depth + 1, limit)
        e, j = parse_term(j, depth + 1, limit)
        return "Divide(%s, %s, %s, %s)" % (a, c2, d, e), j
    if b == 0x9F:
        a, j = parse_term(i + 1, depth + 1, limit)
        c2, j = parse_term(j, depth + 1, limit)
        d, j = parse_term(j, depth + 1, limit)
        e, j = parse_term(j, depth + 1, limit)
        return "Mid(%s, %s, %s, %s)" % (a, c2, d, e), j
    if b in (0x8A, 0x8B, 0x8C, 0x8D, 0x8F):
        a, j = parse_term(i + 1, depth + 1, limit)
        c2, j = parse_term(j, depth + 1, limit)
        d, j = parse_term(j, depth + 1, limit)
        nm = {0x8A: "CreateDWordField", 0x8B: "CreateQWordField", 0x8C: "CreateByteField",
              0x8D: "CreateWordField", 0x8F: "CreateBitField"}[b]
        return "%s(%s, %s, %s)" % (nm, a, c2, d), j
    return "?%02X" % b, i + 1


def parse_block(i, end, depth):
    out = []
    while i < end:
        b = D[i]
        if b in (0xA0, 0xA1, 0xA2):
            v, n = pkg_in(D, i + 1)
            if v is None:
                break
            blk_end = min(i + 1 + n + v, end)
            pad = "  " * depth
            if b == 0xA1:
                out.append(pad + "} Else {")
                i = i + 1 + n
            else:
                t, bs = parse_term(i + 1 + n, depth + 1, blk_end)
                out.append("%s%s (%s) {" % (pad, {0xA0: "If", 0xA2: "While"}[b], t))
                i = bs
            out.extend(parse_block(i, blk_end, depth + 1))
            out.append(pad + "}")
            i = blk_end
            continue
        if b == 0xA3 or b == 0xA6:
            i += 1; continue
        if b == 0xA4:
            t, i = parse_term(i + 1, depth, end)
            out.append("  " * depth + "Return(%s)" % t); continue
        if b == 0xA5:
            out.append("  " * depth + "Break"); i += 1; continue
        if b == 0x08:
            v, n = pkg_in(D, i + 1)
            k = i + 1 + n
            end2 = min(i + 1 + n + v, end)
            nm, k2 = nameseg_in(D, k)
            if nm is None or end2 <= k2:
                i += 1; continue
            t, _ = parse_term(k2, depth + 1, end2)
            out.append("  " * depth + "Name(%s, %s)" % (nm, t))
            i = end2; continue
        if b == 0x10:
            v, n = pkg_in(D, i + 1)
            blk_end = min(i + 1 + n + v, end)
            nm, k2 = nameseg_in(D, i + 1 + n)
            out.append("  " * depth + "Scope(%s) {" % (nm or "?"))
            out.extend(parse_block(k2, blk_end, depth + 1))
            out.append("  " * depth + "}")
            i = blk_end; continue
        t, j = parse_term(i, depth, end)
        if j <= i:
            j = i + 1
        out.append("  " * depth + t)
        i = j
    return out


# ---------- find and decompile ----------
found, i = [], HDR
while True:
    j = D.find(b"\x14", i)
    if j < 0:
        break
    i = j + 1
    v, n = pkg_in(D, j + 1)
    if v is None or v < 4:
        continue
    k = j + 1 + n
    if k + 5 > NL or not is_ns_at(k):
        continue
    name = D[k:k + 4].decode()
    if not re.fullmatch(r"_Q[0-9A-F]{2}", name):
        continue
    argc = D[k + 4]
    body = k + 5
    end = min(j + 1 + n + v, next_after(body, NL))
    if argc > 7 or body >= end:
        continue
    found.append((name, body, end))

print("decompiled %d _Qxx methods (arg-count table: %d entries)\n" % (len(found), len(ARGS)))
for name, body, end in found:
    lines = parse_block(body, end, 0)
    print("=" * 70)
    print("Method(%s)  @0x%06X  %d bytes  -> %d lines" % (name, body, end - body, len(lines)))
    print("=" * 70)
    for ln in lines:
        print(ln)
    print()
