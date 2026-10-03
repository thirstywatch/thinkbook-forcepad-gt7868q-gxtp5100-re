# -*- coding: utf-8 -*-
"""D02. 压缩排查终验 + zlib 魔数命中率的统计显著性 + P=4 变换的全局范围。
"""
import sys, os, zlib, lzma, bz2, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
FW = load(); N = len(FW)

print("=" * 96)
print("D02-a. '78 01' 等 zlib 魔数命中数 vs 随机基线 (判定是否为噪声)")
print("=" * 96)
rng = random.Random(11)
for pat, name in [(b"\x78\x01", "78 01"), (b"\x78\x9c", "78 9C"), (b"\x78\xda", "78 DA"),
                  (b"\x1f\x8b", "1F 8B"), (b"\x5d\x00\x00", "5D 00 00"),
                  (b"\x04\x22\x4d\x18", "04224D18"), (b"\xfd7zXZ\x00", "FD377A585A00")]:
    obs = 0; st = 0
    while True:
        k = FW.find(pat, st)
        if k < 0: break
        obs += 1; st = k + 1
    # 随机基线
    n = len(pat)
    exp = (N - n + 1) * (1/256)**n
    # Monte-Carlo
    mc = []
    for _ in range(200):
        rb = bytes(rng.randrange(256) for _ in range(20000))
        c = 0; s = 0
        while True:
            k = rb.find(pat, s)
            if k < 0: break
            c += 1; s = k + 1
        mc.append(c * (N/20000))
    mc.sort()
    lo, hi = mc[int(200*0.025)], mc[int(200*0.975)]
    print(f"  {name:12s} 观测={obs:>3d}  随机期望={exp:9.3f}  MC95%CI=[{lo:.1f},{hi:.1f}]"
          + ("   <<< 显著超出" if obs > hi else "   (在随机范围内)"))

print("\n" + "=" * 96)
print("D02-b. 逐偏移 zlib 解压尝试 (全文件每 512B 一次, 看是否有任何成功)")
print("=" * 96)
succ = 0
for off in range(0, N - 1024, 512):
    for wbits in (-15, 15, 31):
        try:
            r = zlib.decompress(FW[off:off+4096], wbits)
            if len(r) > 256:
                print(f"  ★ off=0x{off:05X} wbits={wbits} -> {len(r)} B")
                succ += 1
        except Exception:
            pass
print(f"  zlib 成功次数 = {succ}")

print("\n" + "=" * 96)
print("D02-c. ★ P=4 位置掩码适用的全局范围 (判定: 是局部表特性 还是 全局变换)")
print("=" * 96)
mask4 = [0x20, 0x02, 0x04, 0x80]
def is_masked_pair(a, b, ln=512, tol=0):
    if b + ln > N: return False, 0
    x = [FW[a+i] ^ FW[b+i] for i in range(ln)]
    ok = sum(1 for i in range(ln) if x[i] == mask4[i % 4])
    return ok == ln - tol, ok
print("  检验所有 (off, off+512/1024/2048/4096/8192/16384) 对, 看哪些是纯 P=4 掩码:")
hits = []
for a in range(0, N - 512, 512):
    for d in (512, 1024, 2048, 4096, 8192, 16384, 32768, 65536):
        b = a + d
        if b + 512 > N: continue
        ok, n = is_masked_pair(a, b)
        if ok:
            hits.append((a, b, d))
for a, b, d in hits:
    print(f"    0x{a:05X} ^ 0x{b:05X} (d=0x{d:X}) = P4 掩码 [20 02 04 80]")
print(f"  命中数 = {len(hits)}")
ds = sorted(set(d for _, _, d in hits))
print(f"  出现过的距离 d = {[hex(x) for x in ds]}")
offs = sorted(set([a for a, _, _ in hits] + [b for _, b, _ in hits]))
print(f"  涉及的偏移 = {[hex(x) for x in offs]}")
print("\n  => 若都集中在 0x3800/0x5800/0x8600-0x9800/0x19800 附近, 则 P=4 只作用于'数据表副本'")

print("\n" + "=" * 96)
print("D02-d. ★★★ 关键: P=4 掩码是否也适用于 0x01200-0x19850 的任意两个 0x1000 间隔块?")
print("=" * 96)
# 在无表区域测试
cnt_ok = 0; cnt_all = 0
for a in range(0x2000, 0x19800, 0x1000):
    b = a + 0x1000
    if b + 256 > N: continue
    x = [FW[a+i] ^ FW[b+i] for i in range(256)]
    ok = sum(1 for i in range(256) if x[i] == mask4[i % 4])
    cnt_all += 1
    if ok > 240: cnt_ok += 1
print(f"  0x1000 间隔对: 共 {cnt_all} 对, 满足 P=4 掩码(>240/256) 的 = {cnt_ok}")
print("  => 若 cnt_ok≈0, 说明 P=4 掩码 **不** 作用于普通高熵区, 只作用于数据表副本")
