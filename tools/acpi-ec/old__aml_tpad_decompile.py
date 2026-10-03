# -*- coding: utf-8 -*-
"""复用 decompile_qxx.py 的 AML 解析引擎，反编译 DSDT 里 TPAD（触控板）子树的全部方法。

输出：TPID 表 + SBFI/SBFG 描述符 + _HID/_CID/_STA/_CRS/_DSM/TPDS 的伪 ASL。

用法:
  python aml_tpad_decompile.py [DSDT文件]
"""
import os, re, sys, glob, struct

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "..", "acpi-dump")
DSDT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    DIR, "DSDT_LENOVO_CB-01____00000001.bin")
D = open(DSDT, "rb").read()
HDR = 36
NL = len(D)
NC = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")

# ★ 已知的 8 字符外部名（Insyde 在 DSDT 里裸写、无 2E/2F 前缀，定义在本表之外）
#    IICBADR0 = I2C 从机地址资源（定义在 \_SB.PC00.I2C0 所在表，用于 ConcatRes）
EXT_8CHAR = {"IICBADR0", "IICSDA0"}


def pkg_in(d, i):
    """读 AML PkgLength（i 指向首字节）。返回 (值, 总占用字节数)。

    ★ 编码（ACPI 规范 20.2.4，2026-09-29 实测校验）：
        lead 高 2 位 n = 后续字节数；低 4 位是**最低** nibble（bits 0-3）；
        之后 n 个字节依次提供**更高**的位：b[i+1] → bits 4-11，b[i+2] → bits 12-19 …
        ⇒ PkgLength = (lead & 0x0F) | (b[i+1] << 4) | (b[i+2] << 12) | (b[i+3] << 20)
        ⇒ 总占用字节数 = 1 + n；PkgLength 值含自身占用的字节。

    ★ 校验依据（DSDT 实测，421 个 DeviceOp 全扫）：
        - 旧实现 `<< (8*k)` 会让 TPAD(`5B 82 48 3D`) 算出 0x3D48，越界 8 处；
        - 本实现算出 0x3D8，包尾 0x070804 紧随 `10 45 09 2F 04 _SB_PC0`（Scope(_SB.PC00)），
          且全表 420/421 落在文件内、包尾首字节 228 次是 0x5B / 65 次 0xA0 / 58 次 0x10
          / 50 次 0x14，全部是合法 AML 操作符。
        ⇒ 本实现正确；decompile_qxx.py 的旧 pkg_in 已同步修正。
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
    """★ 容错版 NameSeg 解析。

    2026-09-29 实测发现：本 DSDT 里存在 **8 字符名直接裸写**的情况，
    如 `84 49 49 43 42 41 44 52 30`（`ConcatRes(IICBADR0, ...)`）。
    按 ACPI 规范 8 字符名必须写成 `2E IICB ADR0`（DualNamePrefix），
    但 Insyde 这里**省掉了前缀**，属非标准编码（ACPI 反编译器 acpica 也会读乱）。
    本函数据此做容错：无前缀时若紧跟两个 4 字符合法 NameSeg，
    且拼起来的 8 字符名在 DSDT 中确实作为 `Name` 定义存在，则按 8 字符名解析。
    这保证语义正确（否则会把 IICBADR0 错拆成 IICB + ADR0 两个参数）。
    """
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
        # ★ 容错：Insyde 在本 DSDT 里存在**8 字符名裸写**（无 2E/2F 前缀）。
        #   判据（2026-09-29 实测）：
        #     ① 紧跟的两个 4 字符段都是合法 NameSeg；
        #     ② 拼起来的 8 字符名要么在 DSDT 里有 Name 定义，
        #        要么属于已知的**跨表外部引用白名单**（TPID 表引用 IICBADR0，
        #        其定义在 \_SB.PC00.I2C0 所在的表里，本 DSDT 中查不到）。
        #   不加这层容错会把 `IICBADR0` 错拆成 `IICB` + `ADR0` 两个参数，
        #   使 ConcatRes 的实参整体右移一位。
        if i + 8 <= len(d) and all(c in NC for c in d[i + 4:i + 8]):
            eight = d[i:i + 8].decode()
            if eight in EXT_8CHAR or (b"\x08" + d[i:i + 8]) in d:
                return eight, i + 8
        return d[i:i + 4].decode(), i + 4
    return None, i


ARGS = {"_STA": 0, "_INI": 0, "_LID": 0, "_PSR": 0, "_BQC": 0, "_TMP": 0, "_BST": 0,
        "_BIF": 0, "_EC": 0, "_HID": 0, "_UID": 0, "_DSM": 4, "_BCM": 1, "_ON": 0,
        "_OFF": 0, "_CRS": 0, "_ADR": 0, "_S0W": 0, "TPDS": 4}
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
    try:
        scan(open(p, "rb").read())
    except Exception:
        pass


def next_after(x, lim):
    c = [s for s in method_starts if s > x]
    return min(c) if c else lim


def is_ns_at(i):
    if i + 4 > NL:
        return False
    if D[i] in (0x2E, 0x2F):
        return True
    return D[i] in NC and all(c in NC for c in D[i:i + 4])


UN = {0x75: "Increment", 0x76: "Decrement", 0x87: "SizeOf", 0x8E: "ObjectType",
      0x71: "RefOf", 0x83: "DerefOf", 0x92: "LNot"}
BIN3 = {0x72: "Add", 0x74: "Subtract", 0x77: "Multiply", 0x79: "ShiftLeft",
        0x7A: "ShiftRight", 0x7B: "And", 0x7C: "Nand", 0x7D: "Or", 0x7E: "Nor",
        0x7F: "Xor", 0x73: "Concat", 0x84: "ConcatRes", 0x85: "Mod", 0x88: "Index"}
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
        end = min(i + 1 + v, limit)          # ★ 包尾 = 操作符 + PkgLen(含自身)
        return "Buffer(%s){...}" % sz, max(end, k)
    if b in (0x12, 0x13):
        v, n = pkg_in(D, i + 1)
        p = i + 1 + n
        if b == 0x12:
            cnt = D[p]; p += 1
        else:
            cnt, p = parse_term(p, depth + 1, limit)
        end = min(i + 1 + v, limit)          # ★ 包尾
        elems = []
        while p < end and len(elems) < 12:
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
        # ★ 可选第 3 参（Target）：ACPI 规范里 ConcatRes/Mid/Divide 等允许省略 Target
        #   表示"丢弃结果"。编译器省略时不会生成该 term，但静态解析无法只靠长度区分。
        #   判据（2026-09-29 实测得出）：
        #     ① 若第 3 参解析结果**超出本包边界** ⇒ 不存在，回退；
        #     ② 若第 3 参是个**裸 NameString**（无前缀、非 Local/Arg/Index 调用）
        #        且恰好停在包尾 ⇒ 视为**下一条独立语句**，不作为 Target 采用。
        #        依据：ASL 里 Target 必须是"可写引用"，裸名字作 Target 极罕见；
        #        而 Insyde 编译器确实会生成"裸名字当表达式语句"（如 `SBFG`）。
        #   实例：`Return(ConcatRes(IICBADR0, "\_SB.PC00.I2C0"))` + 独立语句 `SBFG`。
        if j < limit:
            save = j
            d, j2 = parse_term(j, depth + 1, limit)
            bare_name = bool(d) and d[0] not in "?(" and "(" not in d and d != "Zero"
            if j2 > limit or (j2 == limit and bare_name and not d.startswith(("Local", "Arg"))):
                d, j = "Zero", save
            else:
                j = j2
        else:
            d = "Zero"
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
    """★ 包尾公式统一为 `op_start + 1 + PkgLen`。

    理由：PkgLength 的**值**已包含 PkgLength 自身占用的字节（ACPI 规范 20.2.4），
    所以 包尾 = 操作符起始 + 1（操作符本身）+ PkgLength 值。
    旧实现写成 `op_start + 1 + n + PkgLen`，**多加了一个 n**，导致 If/While 包体
    被拉长 1~3 字节，解析器读到下一条语句的头字节并误当包内数据 ⇒ 失步（?XX 满屏）。
    """
    out = []
    while i < end:
        b = D[i]
        if b in (0xA0, 0xA1, 0xA2):
            v, n = pkg_in(D, i + 1)
            if v is None:
                break
            blk_end = min(i + 1 + v, end)          # ★ +1 操作符 + v（含自身）
            body_start = i + 1 + n                  # 包体起点 = 操作符 + PkgLength占用
            pad = "  " * depth
            if b == 0xA1:
                # ★ Else：AML 里 A1 是**独立包**，紧跟 If 之后。前一个 If 已经输出过
                #   闭合行 `}`，这里把它**改写成 `} Else {`**（而不是再打一个 `}`），
                #   避免多出一层闭合导致缩进错乱。
                if out and out[-1].strip() == "}":
                    out[-1] = pad + "} Else {"
                else:
                    out.append(pad + "} Else {")
                i = body_start
            else:
                t, bs = parse_term(body_start, depth + 1, blk_end)
                out.append("%s%s (%s) {" % (pad, {0xA0: "If", 0xA2: "While"}[b], t))
                i = min(bs, blk_end)          # ★ 防越界：条件解析不得超包尾
            out.extend(parse_block(i, blk_end, depth + 1))
            out.append(pad + "}")
            i = blk_end
            continue
        if b in (0xA3, 0xA6):
            i += 1; continue
        if b == 0xA4:
            # ★ Return 的表达式解析必须受**当前块边界**约束（end），
            #   否则可选 Target 参数会把后续语句的第一个字当参数吞掉
            #   （实例：`Return(ConcatRes(IICBADR0, "\_SB.PC00.I2C0"))` 误吞 `SBFG`）。
            t, i = parse_term(i + 1, depth, end)
            out.append("  " * depth + "Return(%s)" % t); continue
        if b == 0xA5:
            out.append("  " * depth + "Break"); i += 1; continue
        if b == 0x08:
            # ★ NameOp := 0x08 NameString DataRefObject —— **没有 PkgLength**！
            #   旧实现按 `08 PkgLen NameString Data` 解析是错的（会把 NameString
            #   头两字节误当 PkgLength）。这里直接读 NameString，
            #   对象边界完全由 parse_term 的返回值决定。
            nm, k2 = nameseg_in(D, i + 1)
            if nm is None or k2 >= end:
                i += 1; continue
            t, j2 = parse_term(k2, depth + 1, end)
            out.append("  " * depth + "Name(%s, %s)" % (nm, t))
            i = max(j2, k2 + 1); continue
        if b == 0x10:
            v, n = pkg_in(D, i + 1)
            blk_end = min(i + 1 + v, end)          # ★ 包尾
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


# ---------------- 定位 TPAD 子树并反编译其方法 ----------------
tpads = [m.start() for m in re.finditer(b"TPAD", D)]
DEV = D.rfind(b"\x5b\x82", max(0, tpads[-1] - 0x40), tpads[-1])
v, n = pkg_in(D, DEV + 2)
DEV_END = DEV + 2 + v
print("DSDT: %s" % os.path.basename(DSDT))
print("TPAD Device @0x%06X .. 0x%06X (%d 字节)\n" % (DEV, DEV_END, DEV_END - DEV))

# 目标方法（TPAD 子树内）
WANT = [b"_HID", b"_CID", b"_STA", b"_CRS", b"_DSM", b"TPDS", b"_ADR", b"_UID", b"_S0W"]
hits = []
i = DEV
while i < DEV_END:
    j = D.find(b"\x14", i)
    if j < 0 or j >= DEV_END:
        break
    i = j + 1
    pv, pn = pkg_in(D, j + 1)
    if pv is None or pv < 4:
        continue
    k = j + 1 + pn
    if k + 5 > DEV_END or not is_ns_at(k):
        continue
    name = D[k:k + 4]
    if name not in WANT:
        continue
    argc = D[k + 4]
    body = k + 5
    end = min(j + 1 + pv, DEV_END)      # ★ 包尾 = MethodOp + PkgLen(含自身)
    if argc > 7 or body >= end:
        continue
    hits.append((name.decode(), argc, body, end))

for name, argc, body, end in hits:
    lines = parse_block(body, end, 0)
    print("=" * 70)
    print("Method(%s)  argc=%d  @0x%06X  %d bytes" % (name, argc, body, end - body))
    print("=" * 70)
    for ln in lines:
        print(ln)
    print()

# ---------------- 名称对象（Name(...)）也一起打出 ----------------
print("=" * 70)
print("TPAD 子树里的 Name(...) 对象（含 TPID / SBFI / SBFG）")
print("=" * 70)
TARGET_NAMES = {b"TPID", b"SBFI", b"SBFG", b"SBFB", b"_HID", b"_CID", b"_UID"}
# ★ 用正则直接全扫 NameOp（`08` + NameSeg）。
#   ⚠️ 关键：`NameOp := 0x08 NameString DataRefObject` —— **Name 没有 PkgLength**！
#      早先按 `08 PkgLength NameString Data` 解析是错的，会把 NameString
#      的头两字节误当 PkgLength，导致 421 个 Name 全部解析失败。
#      正确做法：`08` 后直接读 NameString，再用 parse_term 解析对象，其返回值即边界。
name_hits = []
for mo in re.finditer(b"\x08", D[DEV:DEV_END]):
    o = DEV + mo.start()
    nm, k2 = nameseg_in(D, o + 1)
    if nm is None or k2 > DEV_END:
        continue
    name_hits.append((o, nm, k2))

for o, nm, k2 in name_hits:
    short = nm.split(".")[-1]
    if short == "_T_0":
        continue                              # 编译器临时量
    if D[k2] == 0x11:                         # Buffer：原样 dump 内容
        try:
            bv, bn = pkg_in(D, k2 + 1)
            data = D[k2 + 1 + bn:k2 + 1 + bv]
        except Exception:
            data = b""
        print("  Name(%s, Buffer(%d))  @0x%06X" % (nm, len(data), o))
        for r in range(0, len(data), 16):
            print("      %s  |%s|" % (
                " ".join("%02X" % x for x in data[r:r + 16]),
                "".join(chr(x) if 32 <= x < 127 else "." for x in data[r:r + 16])))
        continue
    try:
        t, _ = parse_term(k2, 0, min(k2 + 3000, DEV_END))
    except Exception as e:
        t = "<解析异常 %s>" % e
    if len(t) > 400:
        t = t[:400] + " …(截断)"
    print("  Name(%s, %s)  @0x%06X" % (nm, t, o))
