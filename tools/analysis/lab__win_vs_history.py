# win_vs_history.py — 今晚的窗口读数 vs 12 小时前的历史 dump
#   判据：
#     若同地址内容【跨 12 小时一致】⇒ 窗口是固定/结构性内容（配置表/OTP/闪存映射），不是"活的 RAM"
#     若【大面积不一致】⇒ 窗口是每次运行都变的 RAM
#   纯本地。
import io, re

POC = r"<LAB>\touchpad-lab\poc"

def parse_dump(path):
    """解析 '0xADDR XX XX ...' 形式的 dump，返回 {addr: [bytes]}"""
    mem = {}
    for ln in io.open(path, encoding="utf-8-sig", errors="ignore"):
        ln = ln.strip()
        m = re.match(r"^0x([0-9A-Fa-f]{4})\s+((?:[0-9A-Fa-f]{2}\s*)+)$", ln)
        if not m:
            continue
        a = int(m.group(1), 16)
        bs = [int(x, 16) for x in m.group(2).split()]
        mem[a] = bs
    return mem

def get(mem, addr, n):
    """从 dump 里取 addr 起 n 字节"""
    out = []
    a = addr
    while len(out) < n:
        if a not in mem:
            return None
        chunk = mem[a]
        out.extend(chunk)
        a += len(chunk)
    return out[:n]

snapA = parse_dump(POC + r"\snapA.txt")
snapB = parse_dump(POC + r"\snapB.txt")
snapt = parse_dump(POC + r"\snap-test.txt")
print("snapA 覆盖 %d 个块  行宽 60B  ⇒ 0x%04X..0x%04X" % (
    len(snapA), min(snapA), max(snapA) + len(snapA[max(snapA)]) - 1))
print("snapB 覆盖 %d 个块" % len(snapB))
print()

# 今晚实测（数据段，去掉回复头）
TONIGHT = [
 (0x1000,  16, "0000000000000000004301000050 0100".replace(" ","")[:32]),
 (0x40D0,  24, "00"*24),
 (0x40E8,  18, "00"*18),
 (0x4134,  32, "FF"*32),
 (0x41B4,  16, "E79FF6EBB52E9B111FDF493770012F83"),
 (0x4238,   8, "D79A04433614B724"),
 (0x4240,   8, "4A9DF76B0B2DA3F8"),
 (0x4248,  12, "D5E8C18BE1CFC12E7864D776"),
 (0x4344,  10, "7EF06DB63623AAF1CA4F"),
 (0x6170,  10, "B8D8445C16778DF7AD4E"),
 (0x8000,  10, "FFF4FFF5FFF6FFF7FFF4"),
]
# 修正 0x1000 的期望值（用今晚实际读到的）
TONIGHT[0] = (0x1000, 16, "00000000000000000043010000500100")

print("=" * 96)
print("① 今晚(23:1x) vs 今天 11:09 (snapA) / 11:14 (snapB)：同地址逐字节比对")
print("=" * 96)
print("%-9s %-4s | %-30s | %-12s | %-12s" % ("地址", "长", "今晚实测", "vs snapA", "vs snapB"))
for addr, n, hx in TONIGHT:
    tonight = bytes.fromhex(hx)
    row = []
    for nm, snap in (("A", snapA), ("B", snapB)):
        s = get(snap, addr, n)
        if s is None:
            row.append("(越界/缺)")
        else:
            same = sum(1 for a, b in zip(tonight, s) if a == b)
            row.append("%2d/%2d %s" % (same, n, "★全同" if same == n else ""))
    print("%-9s %-4d | %-30s | %-12s | %-12s" % (
        "0x%04X" % addr, n, hx[:28], row[0], row[1]))
print()
print("  （快照里的实际值，供人工看）")
for addr, n, hx in TONIGHT:
    for nm, snap in (("snapA", snapA), ("snapB", snapB)):
        s = get(snap, addr, n)
        if s:
            print("    %-6s 0x%04X : %s" % (nm, addr, " ".join("%02X" % b for b in s)))
    print("    %-6s 0x%04X : %s" % ("今晚", addr, " ".join("%02X" % b for b in bytes.fromhex(hx))))
    print()

print("=" * 96)
print("② snapA(11:09) vs snapB(11:14)：5 分钟内哪些字节变了")
print("=" * 96)
common = sorted(set(snapA) & set(snapB))
diff_blocks, diff_bytes, total = [], 0, 0
for a in common:
    ca, cb = snapA[a], snapB[a]
    if len(ca) != len(cb):
        diff_blocks.append((a, "长度不同"))
        continue
    d = sum(1 for x, y in zip(ca, cb) if x != y)
    total += len(ca)
    if d:
        diff_bytes += d
        diff_blocks.append((a, d))
print("共同块 %d 个，共 %d 字节；其中【发生变化】的块 %d 个，变化字节 %d 个（%.4f%%）"
      % (len(common), total, len(diff_blocks), diff_bytes, 100.0 * diff_bytes / max(total, 1)))
print("变化块（地址, 变化字节数）：")
for a, d in diff_blocks[:40]:
    print("   0x%04X  %s" % (a, d))
print()
print("=" * 96)
print("③ 窗口整体内容画像（基于 snapA，40KB）")
print("=" * 96)
flat = []
for a in sorted(snapA):
    flat.append((a, snapA[a]))
allb = [b for _, bs in flat for b in bs]
n_all = len(allb)
print("总字节 %d" % n_all)
print("  0x00 占比 %.2f%%    0xFF 占比 %.2f%%" % (
    100.0 * allb.count(0) / n_all, 100.0 * allb.count(255) / n_all))
# 每 0x1000 段的非零率
print("  每 4KB 段的非零字节占比：")
for base in range(0x0000, 0xA000, 0x1000):
    seg = []
    for a in sorted(snapA):
        if base <= a < base + 0x1000:
            seg.extend(snapA[a])
    if not seg:
        continue
    nz = sum(1 for b in seg if b)
    ff = sum(1 for b in seg if b == 255)
    print("    0x%04X-0x%04X  非零 %.1f%%  0xFF %.1f%%" % (base, base + 0xFFF, 100.0*nz/len(seg), 100.0*ff/len(seg)))
