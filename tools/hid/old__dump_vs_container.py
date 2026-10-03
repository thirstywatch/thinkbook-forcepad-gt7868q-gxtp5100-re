"""设备侧 dump vs 容器：若二者同源，可直接判定"芯片读到的是明文还是密文"。
另：定位容器的明文/加扰边界。"""
import os, collections, math

D = r"<WORKSPACE>"
cont = open(os.path.join(D, "touchpad_GT7868Q_fw.bin"), "rb").read()

def ent(b):
    if not b: return 0.0
    c = collections.Counter(b); t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())

for fn in ("device_fw_1E1175.bin", "device_fw_1E3000.bin"):
    p = os.path.join(D, fn)
    if not os.path.exists(p):
        print(fn, "不存在"); continue
    d = open(p, "rb").read()
    print("=== %s  大小=%d  熵=%.4f  ===" % (fn, len(d), ent(d)))
    print("  首 64B:", " ".join("%02X" % x for x in d[:64]))
    print("  首 64B ASCII:", "".join(chr(x) if 32 <= x < 127 else "." for x in d[:64]))
    print("  0x00占比 %.2f%%  0xFF占比 %.2f%%" % (
        100.0 * d.count(0) / len(d), 100.0 * d.count(0xFF) / len(d)))
    # 与容器各段的匹配度
    for name, seg in (("cont[0x0000:0x1400]", cont[0:0x1400]),
                      ("cont[0x1400:0x19A00]", cont[0x1400:0x19A00]),
                      ("cont[0x19A00:]", cont[0x19A00:])):
        n = min(len(d), len(seg))
        eq = sum(1 for i in range(n) if d[i] == seg[i]) / n
        x = collections.Counter(a ^ b for a, b in zip(d[:n], seg[:n]))
        top = x.most_common(3)
        print("   vs %-22s 逐字节相等率=%.4f(=%.1f/256)  最常见异或=%s" % (
            name, eq, eq * 256, ", ".join("%02X:x%d" % t for t in top)))
    print()

# 容器明文/加扰边界定位：滑动窗熵（步长 0x100）
print("=== 容器熵剖面（窗口 0x400，步长 0x200；找结构/随机的交界）===")
for off in range(0, len(cont) - 0x400, 0x200):
    e = ent(cont[off:off + 0x400])
    if off < 0x2400 or off > 0x18800:
        print("  0x%06X  %.3f" % (off, e))
