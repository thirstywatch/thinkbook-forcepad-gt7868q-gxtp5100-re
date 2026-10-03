# win_v1v2_link.py — ① v2 地址 0x200040D0 与 v1 地址 0x2000 是不是同一条记录？
#                  ② 0x8000-0x9FFF 到底是"活数据"还是"内存自检图案"？（关系到我 §12.3 的论证）
import io, re, struct

POC = r"<LAB>\touchpad-lab\poc"
def load(fn):
    mem = {}
    for ln in io.open(POC + "\\" + fn, encoding="utf-8-sig", errors="ignore"):
        m = re.match(r"^0x([0-9A-Fa-f]{4})\s+((?:[0-9A-Fa-f]{2}\s*)+)$", ln.strip())
        if m:
            mem[int(m.group(1), 16)] = bytes(int(x, 16) for x in m.group(2).split())
    lo = min(mem); hi = max(mem) + len(mem[max(mem)])
    buf = bytearray(b"\x00" * (hi - lo))
    for a, bs in mem.items():
        buf[a - lo:a - lo + len(bs)] = bs
    return bytes(buf), lo

A, lo = load("snapA.txt")

# 今晚 v2 MEM2 200040D0 返回的数据段（60B，从 vib-link 输出抄录，前 32 可见，其余为 0）
V2 = bytes.fromhex("0000030001401F0003000000000000006605120008070000" + "00"*8)

print("=" * 92)
print("① v2@0x200040D0  与  v1@0x2000  比对")
print("=" * 92)
for addr in (0x2000, 0x2001, 0x1FF0, 0x1FFC):
    seg = A[addr-lo:addr-lo+24]
    same = sum(1 for x, y in zip(V2, seg) if x == y)
    print("  v1@0x%04X : %s   -> 与 v2 逐字节相同 %d/24" % (
        addr, " ".join("%02X" % b for b in seg), same))
print("  v2 数据段: %s" % " ".join("%02X" % b for b in V2[:24]))
print()
print("  ⇒ 若 0x2000 那一行近乎全同，说明【v2 的 0x200040D0 读的就是 v1 的 0x2000 这条记录】")
print()
print("  0x2000 起 60 字节（快照原文）:")
for off in range(0, 60, 20):
    s = 0x2000 + off
    row = A[s-lo:s-lo+20]
    asc = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
    print("    0x%04X  %-59s |%s|" % (s, " ".join("%02X" % b for b in row), asc))

print()
print("=" * 92)
print("② 0x8000-0x9FFF：是活数据还是内存自检图案？")
print("=" * 92)
for base in (0x8000, 0x8100, 0x8200, 0x8400, 0x8800, 0x9000, 0x9200, 0x9400, 0x9800, 0x9C00):
    row = A[base-lo:base-lo+32]
    asc = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
    print("  0x%04X  %-95s |%s|" % (base, " ".join("%02X" % b for b in row), asc))

print()
print("  -- 该区间的 16 位取值分布（看是否呈'图案'而非连续量）--")
seg = A[0x8000-lo:0xA000-lo]
u16 = [struct.unpack_from(">H", seg, i)[0] for i in range(0, len(seg)-1, 2)]
from collections import Counter
c = Counter(u16)
print("   u16BE 唯一值 %d 个；出现最多的 12 个: %s" % (len(c), c.most_common(12)))
print("   值域: min=0x%04X max=0x%04X" % (min(u16), max(u16)))
hi_hist = Counter((v >> 8) for v in u16)
print("   高字节直方图（前 12）: %s" % hi_hist.most_common(12))

print()
print("  -- 逐字节：单字节值分布 --")
cb = Counter(seg)
print("   最常见 12 个字节值: %s" % cb.most_common(12))
# 是否只有少数几种值（图案特征）？
top = cb.most_common(8)
cov = sum(n for _, n in top) / len(seg)
print("   前 8 种值占比 %.1f%%（越高越像图案/填充，不像数据）" % (100.0 * cov))
