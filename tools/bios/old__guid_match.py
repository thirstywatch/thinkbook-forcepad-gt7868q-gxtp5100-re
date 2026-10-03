"""把 PE 里扫到的 GUID 与 EDK2 官方 GUID 库批量比对。

用法: python guid_match.py <file.bin> [--all]
默认只扫可执行段 + 数据段里"看起来像 GUID"的 16 字节块。
"""
import sys, struct, re, os

sys.path.insert(0, ".")
from pe_dis import ffs_body, pick_pe, pe_info


def load_edk2_guids(path="edk2_guids.py"):
    """把 edk2_guids.py 里的字典解析成 {GUID字符串: 名字}"""
    src = open(path, encoding="utf-8", errors="replace").read()
    # 形如: "gEfiFooGuid": [0x1234, 0x5678, 0x9abc, 0xde, 0xf0, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66],
    pat = re.compile(
        r'"([^"]+)"\s*:\s*\[\s*'
        r'(0x[0-9a-fA-F]+)\s*,\s*(0x[0-9a-fA-F]+)\s*,\s*(0x[0-9a-fA-F]+)\s*,\s*'
        r'(0x[0-9a-fA-F]+)\s*,\s*(0x[0-9a-fA-F]+)\s*,\s*'
        r'(0x[0-9a-fA-F]+)\s*,\s*(0x[0-9a-fA-F]+)\s*,\s*'
        r'(0x[0-9a-fA-F]+)\s*,\s*(0x[0-9a-fA-F]+)\s*,\s*'
        r'(0x[0-9a-fA-F]+)\s*,\s*(0x[0-9a-fA-F]+)\s*',
        re.M)
    out = {}
    for m in pat.finditer(src):
        name = m.group(1)
        v = [int(m.group(i), 16) for i in range(2, 13)]
        key = guid_str(v)
        out[key] = name
    return out


def guid_str(v):
    """v = [d1, d2, d3, b0..b7]"""
    d1, d2, d3 = v[0], v[1], v[2]
    b = v[3:11]
    return "%08X-%04X-%04X-%02X%02X-%02X%02X%02X%02X%02X%02X" % (
        d1, d2, d3, b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7])


def guid_at(pe, info, va):
    for name, va0, vsz, pra, rsz, ch in info["secs"]:
        s = info["base"] + va0
        if s <= va < s + max(vsz, rsz):
            f = pra + (va - s)
            b = pe[f:f + 16]
            if len(b) < 16:
                return None
            d1, d2, d3 = struct.unpack_from("<IHH", b, 0)
            return "%08X-%04X-%04X-%s-%s" % (
                d1, d2, d3, b[8:10].hex().upper(), b[10:16].hex().upper())
    return None


def main():
    path = sys.argv[1]
    d, secs = ffs_body(path)
    st, pe, off = pick_pe(secs)
    info = pe_info(pe)
    db = load_edk2_guids()
    print("# EDK2 官方 GUID 库: %d 条" % len(db))
    print("# %s" % path)
    print()

    # 扫所有非 .reloc 段，按 4 字节步进找 GUID（GUID 可能不对齐到 8/16）
    # 但先按 16 字节对齐扫（编译器通常对齐）
    hits = []
    for name, va0, vsz, pra, rsz, ch in info["secs"]:
        if name in (".reloc", ".xdata"):
            continue
        s = info["base"] + va0
        for k in range(0, rsz - 16, 4):
            g = guid_at(pe, info, s + k)
            if g and g in db:
                hits.append((s + k, g, db[g]))

    seen = set()
    for va, g, nm in sorted(hits):
        if (g, nm) in seen:
            continue
        seen.add((g, nm))
        print("  0x%06X  %-11s %s" % (va, nm.replace("Guid", ""), g))

    # 再列所有不在库里的"像 GUID"的块（.data 段、16 字节对齐、且段内非代码）
    print()
    print("# 未在 EDK2 库中命中的 GUID（.data 段内、按 16 对齐）：")
    for name, va0, vsz, pra, rsz, ch in info["secs"]:
        if not (name.startswith(".data") or name in ("", ".rdata")):
            continue
        s = info["base"] + va0
        for k in range(0, rsz - 16, 16):
            g = guid_at(pe, info, s + k)
            if not g:
                continue
            lo = g.replace("-", "").lower()
            # 过滤明显非 GUID（全 0、全 FF、单调字节）
            if lo == "0" * 32 or lo == "f" * 32:
                continue
            b = bytes.fromhex(lo)
            if len(set(b)) < 6:
                continue
            if g in db:
                continue
            print("  0x%06X  %s" % (s + k, g))


if __name__ == "__main__":
    main()
