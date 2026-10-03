"""PE32+ 交叉引用分析器。

用途：把"某地址被哪些指令引用"与"某指令引用了什么"变成可查询的数据。
三个能力：
  1. call/jmp 目标直方图 -> 函数入口候选（被调用次数排序）
  2. 全量 rip-relative 内存引用 -> {目标地址: [引用点...]} 倒排表
  3. 给定目标地址，反查引用点上下文（定位字符串/GUID 的使用者）

用法：
  python xref.py <file.bin> funcs             # 函数入口候选
  python xref.py <file.bin> xref <hexaddr>    # 谁引用了某地址
  python xref.py <file.bin> around <hexaddr> [n]  # 打印某地址附近的指令
  python xref.py <file.bin> strrefs           # 所有指向可打印字符串的引用
"""
import struct, sys, re
from collections import Counter, defaultdict

sys.path.insert(0, ".")
from pe_dis import ffs_body, pick_pe, pe_info


def load(path):
    d, secs = ffs_body(path)
    st, pe, off = pick_pe(secs)
    info = pe_info(pe)
    return pe, info


def insn_text(mn, ops):
    return "%s %s" % (mn, ops) if ops else mn


def iter_insns(pe, info, md):
    """yield (addr, mnemonic, op_str, size, bytes)"""
    EXEC = 0x20000000
    CODE = 0x00000020
    for name, va, vsz, pra, rsz, ch in info["secs"]:
        if not (ch & (EXEC | CODE)):
            continue
        code = pe[pra:pra + rsz]
        base = info["base"] + va
        off = 0
        while off < len(code):
            got = list(md.disasm(code[off:], base + off))
            if got:
                for i in got:
                    yield (i.address, i.mnemonic, i.op_str, i.size,
                           code[i.address - base:i.address - base + i.size])
                off += sum(i.size for i in got)
            else:
                off += 1


def rva_to_file(pe, info, target):
    """把 VA 映射到 PE 文件偏移（跨所有段）"""
    for name, va, vsz, pra, rsz, ch in info["secs"]:
        s = info["base"] + va
        if s <= target < s + max(vsz, rsz):
            f = pra + (target - s)
            if 0 <= f < len(pe):
                return f
    return None


def read_str(pe, info, target, maxlen=120):
    f = rva_to_file(pe, info, target)
    if f is None:
        return None
    # ASCII
    e = f
    while e < len(pe) and e - f < maxlen and 32 <= pe[e] < 127:
        e += 1
    if e - f >= 5:
        return ("ASC", pe[f:e].decode("latin1"))
    # UTF-16LE
    e = f; n = 0
    while e + 1 < len(pe) and n < maxlen:
        lo, hi = pe[e], pe[e + 1]
        if hi == 0 and 32 <= lo < 127:
            e += 2; n += 1
        else:
            break
    if n >= 5:
        return ("U16", pe[f:f + n * 2].decode("utf-16-le"))
    return None


def main():
    import capstone
    path = sys.argv[1]
    cmd = sys.argv[2] if len(sys.argv) > 2 else "funcs"
    pe, info = load(path)
    mode = capstone.CS_MODE_64 if info["magic"] == 0x20B else capstone.CS_MODE_32
    md = capstone.Cs(capstone.CS_ARCH_X86, mode)
    md.detail = True

    print("# %s  base=0x%X magic=0x%X entry=0x%X" % (
        path, info["base"], info["magic"], info["ep"]))
    print("# 段: " + ", ".join(
        "%s(va=0x%X vsz=0x%X rsz=0x%X ch=0x%X)" % (n, v, vz, rz, c)
        for n, v, vz, p, rz, c in info["secs"]))
    print()

    # ---------- 收集 ----------
    call_targets = Counter()          # 直接 call 目标
    addr_refs = defaultdict(list)     # {rip 目标地址: [(引用点addr, 文本)]}
    str_refs = defaultdict(list)      # {目标: [(引用点, 类型, 文本)]}
    n = 0

    for addr, mn, ops, size, raw in iter_insns(pe, info, md):
        n += 1
        if mn in ("call", "jmp") and ops and re.fullmatch(r"0x[0-9a-f]+", ops):
            call_targets[int(ops, 16)] += 1
        # rip-relative：capstone 给 [rip + 0xXXXX]，换算成绝对地址
        m = re.search(r"\[rip \+ (0x[0-9a-f]+)\]", ops)
        if m:
            tgt = addr + size + int(m.group(1), 16)
            addr_refs[tgt].append((addr, insn_text(mn, ops)))
        # 32 位模式：绝对寻址 [0xXXXXXXX]
        if info["magic"] != 0x20B:
            m2 = re.search(r"\[(0x[0-9a-f]{6,8})\]", ops)
            if m2:
                addr_refs[int(m2.group(1), 16)].append((addr, insn_text(mn, ops)))

    print("# 扫描指令 %d 条 / 唯一 rip 目标 %d 个 / 唯一 call 目标 %d 个"
          % (n, len(addr_refs), len(call_targets)))
    print()

    if cmd == "funcs":
        print("# 被直接 call 最多的目标（函数入口候选，排除库函数区）")
        for t, c in call_targets.most_common(60):
            print("  0x%06X  x%d" % (t, c))
        print()
        print("# 被直接 jmp 的目标（尾部跳转/跳板，前 30）")
        jt = Counter()
        for addr, mn, ops, size, raw in iter_insns(pe, info, md):
            pass
        return

    if cmd == "xref":
        tgt = int(sys.argv[3], 16)
        print("# 引用 0x%X 的位置：" % tgt)
        for a, t in addr_refs.get(tgt, []):
            s = read_str(pe, info, tgt)
            print("  0x%06X: %-40s" % (a, t))
        if not addr_refs.get(tgt):
            print("   (无)")
        # 也看是否是 call 目标
        if tgt in call_targets:
            print("# 该地址被 call %d 次" % call_targets[tgt])
        return

    if cmd == "around":
        tgt = int(sys.argv[3], 16)
        k = int(sys.argv[4]) if len(sys.argv) > 4 else 40
        lo, hi = tgt - k * 8, tgt + k * 8
        print("# 0x%X 附近：" % tgt)
        for addr, mn, ops, size, raw in iter_insns(pe, info, md):
            if lo <= addr < hi:
                mark = " <<<" if addr == tgt else ""
                print("  0x%06X  %-8s %-42s%s" % (addr, mn, ops, mark))
        return

    if cmd == "strrefs":
        print("# 指向可打印字符串的引用：")
        rows = []
        for tgt, refs in addr_refs.items():
            s = read_str(pe, info, tgt)
            if s:
                rows.append((tgt, s, refs))
        rows.sort(key=lambda r: r[0])
        for tgt, (kind, s), refs in rows:
            print("  0x%06X %s %r  <- %s" % (
                tgt, kind, s[:80],
                " ".join("0x%X" % a for a, _ in refs[:6])))
        return


if __name__ == "__main__":
    main()
