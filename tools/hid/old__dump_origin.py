"""定位 device_fw_*.bin 的来源与性质：是不是从 cap_payload.bin / 容器里切出来的？
它本身是明文还是密文？"""
import os, re, collections, math

D = r"<WORKSPACE>"

def ent(b):
    if not b: return 0.0
    c = collections.Counter(b); t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())

srcs = {}
for fn in ("cap_payload.bin", "touchpad_GT7868Q_fw.bin", "gt7868q.bin",
           "touchpad_TF100A_thumb.asm.txt"):
    p = os.path.join(D, fn)
    if os.path.exists(p):
        srcs[fn] = open(p, "rb").read()
        print("源 %-32s %d 字节" % (fn, len(srcs[fn])))

for fn in ("device_fw_1E1175.bin", "device_fw_1E3000.bin"):
    d = open(os.path.join(D, fn), "rb").read()
    print("\n=== %s  %d 字节 ===" % (fn, len(d)))
    # 头部指纹：用前 32 字节在源文件里找
    head = d[:32]
    found = False
    for sfn, sd in srcs.items():
        idx = sd.find(head)
        while idx >= 0:
            print("  ★ 前 32B 命中 %s 偏移 0x%X" % (sfn, idx))
            found = True
            idx = sd.find(head, idx + 1)
            if idx > 0 and found: break
    if not found:
        print("  前 32B 在已知源中未命中（可能是设备直接读回的）")

    # 是否明文：可打印 ASCII 串 + 长 0x00/0xFF 游程
    strs = re.findall(rb"[\x20-\x7e]{6,}", d)
    print("  可打印 ASCII 串（>=6）共 %d 条，最长 %d" % (
        len(strs), max((len(s) for s in strs), default=0)))
    for s in strs[:15]:
        print("     ", s.decode('latin-1')[:70])
    runs = {}
    for b in (0x00, 0xFF):
        mx = cur = 0
        for x in d:
            cur = cur + 1 if x == b else 0
            mx = max(mx, cur)
        runs[b] = mx
        print("  最长 %02X 游程 = %d 字节" % (b, mx))
    print("  熵=%.4f  0x00=%.2f%%  0xFF=%.2f%%" % (
        ent(d), 100.0 * d.count(0) / len(d), 100.0 * d.count(0xFF) / len(d)))

    # 分块熵剖面（每 0x2000）
    print("  分块熵剖面：")
    for off in range(0, len(d), 0x2000):
        print("     0x%06X  %.3f" % (off, ent(d[off:off + 0x2000])))
