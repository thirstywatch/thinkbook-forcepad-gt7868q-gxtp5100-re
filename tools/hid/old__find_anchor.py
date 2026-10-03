"""A③ 找锚点：在 capsule / X9-15 产物里找"同一固件的第二份（最好是明文）拷贝"。
锚点是决定 1 KiB 变换能否被解开的唯一前提。"""
import os, re, collections, math

FW = r"<WORKSPACE>"
X9 = r"<WORKSPACE>"

def ent(b):
    if not b: return 0.0
    c = collections.Counter(b); t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())

cont = open(os.path.join(FW, "touchpad_GT7868Q_fw.bin"), "rb").read()
cap = open(os.path.join(FW, "cap_payload.bin"), "rb").read()
print("container = %d B ; cap_payload = %d B" % (len(cont), len(cap)))

# ① 容器是不是 cap_payload 的切片？
hea = cont[:32]
i = cap.find(hea)
print("\n① 容器头 32B 在 cap_payload 中的位置: %s" % (("0x%X" % i) if i >= 0 else "未命中"))
if i >= 0:
    # 该处往后的 161628 字节是否就是容器
    seg = cap[i:i + len(cont)]
    same = sum(1 for a, b in zip(seg, cont) if a == b) / len(cont)
    print("   该处起 %d 字节 vs 容器 逐字节相等率 = %.6f" % (len(cont), same))

# ② "YELSTO" 在哪些地方出现（明文锚点候选）
print("\n② b'YELSTO' 出现位置：")
for nm, d in (("container", cont), ("cap_payload", cap)):
    pos = [m.start() for m in re.finditer(b"YELSTO", d)]
    print("   %-12s %d 处: %s" % (nm, len(pos), ", ".join("0x%X" % p for p in pos[:12])))
print("   b'7868' 出现位置：")
for nm, d in (("container", cont), ("cap_payload", cap)):
    pos = [m.start() for m in re.finditer(rb"7868", d)]
    print("   %-12s %d 处: %s" % (nm, len(pos), ", ".join("0x%X" % p for p in pos[:12])))

# ③ cap_payload 里有没有容器的第二份拷贝（用容器明文段的特征串）
print("\n③ 用容器 0x0000-0x1000 明文段的多条特征串在 cap_payload 里找拷贝：")
probes = [cont[0x0B0:0x0C0], cont[0x100:0x110], cont[0x200:0x210], cont[0x800:0x810]]
for k, p in enumerate(probes):
    pos = [m.start() for m in re.finditer(re.escape(p), cap)]
    print("   probe#%d (%d B) -> %d 处 %s" % (k, len(p), len(pos),
          ", ".join("0x%X" % x for x in pos[:8])))

# ④ cap_payload 里其他高熵子镜像的头
print("\n④ cap_payload 中的可识别子镜像头：")
for magic in (b"BTFW", b"GTFW", b"YELS", b"GFW\x00", b"FWUP"):
    pos = [m.start() for m in re.finditer(re.escape(magic), cap)]
    if pos:
        print("   %-6s %d 处: %s" % (magic.decode(), len(pos),
              ", ".join("0x%X" % x for x in pos[:8])))

# ⑤ X9-15 产物
print("\n⑤ X9-15 产物：")
for root, dirs, files in os.walk(X9):
    for f in files:
        p = os.path.join(root, f)
        try:
            sz = os.path.getsize(p)
        except OSError:
            continue
        if sz > 4096 and not f.lower().endswith((".py", ".md", ".txt", ".exe", ".iso")):
            print("   %-14s %9d B" % (f, sz))

for fn in ("deliverables/DSDT_X9-15.bin", "out_sc1/N4C_SC1_blob03_dec.bin"):
    p = os.path.join(X9, fn)
    if os.path.exists(p):
        d = open(p, "rb").read()
        print("\n   --- %s  %d B  熵=%.4f ---" % (fn, len(d), ent(d)))
        print("      首 64B:", " ".join("%02X" % x for x in d[:64]))
        print("      ASCII :", "".join(chr(x) if 32 <= x < 127 else "." for x in d[:64]))
        for magic in (b"YELSTO", b"7868", b"BTFW"):
            pos = [m.start() for m in re.finditer(re.escape(magic), d)]
            if pos:
                print("      %s 出现 %d 处: %s" % (magic.decode(), len(pos),
                      ", ".join("0x%X" % x for x in pos[:8])))
