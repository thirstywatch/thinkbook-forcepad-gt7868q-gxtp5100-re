# col04_window_correlate.py — 把真机读窗口的实测字节，拿去固件容器里搜
#   目的：区分两种可能
#     X1 读窗口不是 TF100A 的 RAM（我上一轮的判断）
#     X2 读窗口是 TF100A 的 RAM，但【文档里那份 TF100A 固件镜像不准/不是同一版本】
#   纯本地分析，不碰设备。
import struct, io

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
full = open(BIN, 'rb').read()
N = len(full)
OFF_PLAIN = 0x19ABC          # 明文段（TF100A 镜像）在容器中的起点
plain = full[OFF_PLAIN:]     # 56,480 B
enc   = full[:OFF_PLAIN]     # 105,148 B（高熵，GT7868Q 侧）
print("容器 %d B | 高熵段 %d B | 明文段 %d B" % (N, len(enc), len(plain)))
print()

# ── 真机实测到的窗口内容（数据段，已去掉回复头）──────────────────
W = [
 (0x1000, 16, "0000000000000000004301000050010 0".replace(" ","")),
 (0x40D0, 24, "00"*24),
 (0x40E8, 18, "00"*18),
 (0x4134, 32, "FF"*32),
 (0x41B4, 16, "E79FF6EBB52E9B111FDF493770012F83"),
 (0x4238,  8, "D79A04433614B724"),
 (0x4240,  8, "4A9DF76B0B2DA3F8"),
 (0x4248, 12, "D5E8C18BE1CFC12E7864D776"),
 (0x4344, 10, "7EF06DB63623AAF1CA4F"),
 (0x6170, 10, "B8D8445C16778DF7AD4E"),
 (0x8000, 10, "FFF4FFF5FFF6FFF7FFF4"),
 (0x200040D0,32,"0000030001401F0003000000000000006605120008070000" + "00"*8),  # v2 块（前32B）
]

def hexb(s):
    return bytes.fromhex(s)

print("="*78)
print("① 同地址直比：窗口[addr] vs 镜像[addr]")
print("="*78)
print("%-12s %-10s %s" % ("addr", "对比对象", "结果"))
for addr, ln, hx in W:
    if addr > 0xFFFF:
        continue
    w = hexb(hx)[:ln]
    for nm, img in (("明文段(镜像)", plain), ("高熵段", enc)):
        if addr + ln <= len(img):
            seg = img[addr:addr+ln]
            same = sum(1 for a, b in zip(w, seg) if a == b)
            print("%-12s %-10s 逐字节相同 %2d/%2d   %s" % (
                "0x%04X" % addr, nm, same, ln,
                "★命中" if same == ln else ("(nz=%d)" % sum(1 for b in seg if b))))
    print()

print("="*78)
print("② 子串搜索：把窗口里的【高熵片段】拿到整个容器里找")
print("="*78)
needles = [hx for _, _, hx in W if len(hx) >= 16 and len(set(hexb(hx))) > 6]
for hx in needles:
    nd = hexb(hx)
    hits_full = [m for m in range(len(full)) if full.startswith(nd, m)]
    hits_plain = [m for m in range(len(plain)) if plain.startswith(nd, m)]
    hits_enc = [m for m in range(len(enc)) if enc.startswith(nd, m)]
    print("  %s …  容器:%d 处 %s | 明文段:%d 处 %s | 高熵段:%d 处 %s" % (
        hx[:24], len(hits_full), ["0x%X" % x for x in hits_full[:3]],
        len(hits_plain), ["0x%X" % x for x in hits_plain[:3]],
        len(hits_enc), ["0x%X" % x for x in hits_enc[:3]]))

print()
print("="*78)
print("③ 反向：镜像在这几个偏移处到底是什么？（看窗口该不该等于它）")
print("="*78)
for addr in (0x1000, 0x40D0, 0x40E8, 0x4134, 0x41B4, 0x4238, 0x4344, 0x6170, 0x8000):
    def d(img):
        if addr + 16 > len(img):
            return "(越界)"
        return " ".join("%02X" % b for b in img[addr:addr+16])
    print("  0x%04X  明文段: %-50s" % (addr, d(plain)))
    print("         高熵段: %s" % d(enc))

print()
print("="*78)
print("④ 窗口 0x8000 的步进图案 'FFF4 FFF5 FFF6 FFF7' 在容器里有没有")
print("="*78)
for pat, nm in [(bytes.fromhex("FFF4FFF5FFF6FFF7"), "F4F5F6F7 步进"),
                (bytes.fromhex("F4FFF5FFF6FFF7"), "字节步进"),
                (bytes.fromhex("FFF4"), "FFF4")]:
    hits = [m for m in range(len(full)) if full.startswith(pat, m)]
    print("  %-14s 命中 %d 处 %s" % (nm, len(hits), ["0x%X" % x for x in hits[:6]]))
