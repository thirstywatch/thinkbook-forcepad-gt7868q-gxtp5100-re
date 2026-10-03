"""若加扰是"周期 1024 的弱变换"，那么第 j 个偏移处（j=0..1023）在所有 1KiB 块里的
密文字节分布 = 明文字节分布做同一个固定变换。
=> 明文里大量重复的字节（填充 0x00/0xFF、对齐）会让该偏移出现"众数"。
=> 用众数直接当密钥（假设明文众数是 0x00），做试验性解密并评估可读性。
"""
import os, collections, math

D = r"<WORKSPACE>"
seg = open(os.path.join(D, "touchpad_GT7868Q_fw.bin"), "rb").read()[0x1400:0x19A00]
n = len(seg)
L = 1024

mode_frac = []
key = bytearray(L)
for j in range(L):
    cls = seg[j::L]
    c = collections.Counter(cls)
    v, k = c.most_common(1)[0]
    mode_frac.append(k / len(cls))
    key[j] = v

mode_frac.sort()
print("每个偏移(0..1023)的众数占比分布：")
for q in (0.0, 0.25, 0.5, 0.75, 0.9, 1.0):
    i = min(int(q * (len(mode_frac) - 1)), len(mode_frac) - 1)
    print("   %-5s %.4f" % ("%.0f%%" % (q * 100), mode_frac[i]))
print("   均匀随机基线 ≈ 1/256 = 0.0039，样本数 ≈", len(seg[0::L]))

# 试验性解密：假设明文众数 = 0x00 => K = 众数；若明文众数=0xFF => K = 众数^0xFF
def entropy(b):
    c = collections.Counter(b); t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())

for const, nm in ((0x00, "假设明文众数=0x00"), (0xFF, "假设明文众数=0xFF")):
    dec = bytes(b ^ k ^ const for b, k in zip(seg, (key[i % L] for i in range(n))))
    # 统计可打印 ASCII 串
    import re
    strs = re.findall(rb"[\x20-\x7e]{6,}", dec)
    print("\n%s -> 解密后熵=%.3f, 可打印串 %d 条" % (nm, entropy(dec), len(strs)))
    for s in strs[:12]:
        print("     ", s[:60])
    # 头 32 字节
    print("      头 32B:", " ".join("%02X" % x for x in dec[:32]))
