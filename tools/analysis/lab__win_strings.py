# win_strings.py — 把历史 40KB 快照拼成连续缓冲，做结构分析
#   ① 可打印字符串  ② 魔数  ③ 0x0800xxxx 代码指针（Cortex-M RAM 的标志） ④ 区块分类
import io, re, math, struct

POC = r"<LAB>\touchpad-lab\poc"

def load(path):
    mem = {}
    for ln in io.open(path, encoding="utf-8-sig", errors="ignore"):
        m = re.match(r"^0x([0-9A-Fa-f]{4})\s+((?:[0-9A-Fa-f]{2}\s*)+)$", ln.strip())
        if m:
            mem[int(m.group(1), 16)] = bytes(int(x, 16) for x in m.group(2).split())
    return mem

for tag, fn in (("snapA (11:09)", "snapA.txt"), ("snapB (11:14)", "snapB.txt")):
    mem = load(POC + "\\" + fn)
    if not mem:
        print("%s: 解析为空" % tag); continue
    lo, hi = min(mem), max(mem) + len(mem[max(mem)])
    buf = bytearray(b"\x00" * (hi - lo))
    for a, bs in mem.items():
        buf[a - lo:a - lo + len(bs)] = bs
    buf = bytes(buf)
    print("=" * 84)
    print("%s : 块 %d, 覆盖 0x%04X..0x%04X (%d B), 非零 %.1f%%" % (
        tag, len(mem), lo, hi - 1, len(buf),
        100.0 * sum(1 for b in buf if b) / len(buf)))
    print("=" * 84)

    print("\n-- ① 可打印字符串（>=4 字符）--")
    n = 0
    for m in re.finditer(rb"[\x20-\x7e]{4,}", buf):
        print("   0x%04X  %r" % (lo + m.start(), m.group().decode()))
        n += 1
        if n >= 30: break
    print("   共 %d 条" % n)

    print("\n-- ② 魔数 / 特征 --")
    for pat, nm in [(b"\x5a\xa5", "5A A5 同步字"), (b"TF100", "TF100"), (b"GXTP", "GXTP"),
                    (b"7868", "7868"), (b"Goodix", "Goodix"), (b"GDX", "GDX"),
                    (b"\xa5\x5a", "A5 5A 反序"), (b"FW", "FW")]:
        h = [lo + m.start() for m in re.finditer(re.escape(pat), buf)]
        print("   %-16s 命中 %3d 处 %s" % (nm, len(h), ["0x%04X" % x for x in h[:6]]))

    print("\n-- ③ 0x0800xxxx 代码指针（Cortex-M RAM 里应有）--")
    ptrs = []
    for off in range(0, len(buf) - 4, 2):
        v = struct.unpack_from("<I", buf, off)[0]
        if 0x08000000 <= v < 0x08100000:
            ptrs.append((lo + off, v))
    print("   命中 %d 个" % len(ptrs))
    for a, v in ptrs[:25]:
        print("     0x%04X -> 0x%08X" % (a, v))

    print("\n-- ④ 512B 区块分类 --")
    def ent(d):
        if not d: return 0.0
        c = [0] * 256
        for b in d: c[b] += 1
        e = 0.0
        for x in c:
            if x:
                p = x / len(d); e -= p * math.log2(p)
        return e
    cls = []
    for base in range(0, len(buf), 0x200):
        d = buf[base:base + 0x200]
        if not d: continue
        nz = sum(1 for b in d if b); ff = sum(1 for b in d if b == 255); e = ent(d)
        if nz == 0: k = "全零"
        elif ff == len(d): k = "全FF"
        elif e > 7.0: k = "高熵%.1f" % e
        elif e < 2.0: k = "低熵%.1f" % e
        else: k = "中熵%.1f" % e
        cls.append((lo + base, k))
    i = 0
    while i < len(cls):
        b, k = cls[i]; j = i
        while j + 1 < len(cls) and cls[j + 1][1] == k and cls[j + 1][0] == cls[j][0] + 0x200:
            j += 1
        print("   0x%04X-0x%04X  %s" % (b, cls[j][0] + 0x1FF, k))
        i = j + 1
    print()
