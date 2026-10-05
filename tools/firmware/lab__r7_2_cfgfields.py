# -*- coding: utf-8 -*-
"""R7-2: 本机 cfg 的「机型相关字段」定位
  ① libinput 硬数字当自证锚点  ② 机型轴（capA==capB 且 != 本机）标出型号专有字节
  ③ X/Y 分辨率：u16 对且比值≈面板长宽比"""
import numpy as np

S = {'本机': ('orig_TB14P.bin', 0x113C), 'capA': ('cap22001E0D.Cap', 0x4F0),
     'capB': ('cap26002816.Cap', 0x4F0)}
BODY = {}
for k, (p, img) in S.items():
    BODY[k] = open(p, 'rb').read()[:img]

ours = BODY['本机'][0x4C:0x4C + 1024]
print(f"本机 config body @0x4C 1024 B: {ours[:16].hex(' ')}")
print("  4 份冗余自检: " + " ".join(
    str(BODY['本机'][0x4C + i * 1084:0x4C + i * 1084 + 1024] == ours) for i in (1, 2, 3)))


def find_body(w, ref):
    wa = np.frombuffer(w, dtype=np.uint8); ra = np.frombuffer(ref, dtype=np.uint8)
    best = (0, -1.0)
    for off in range(0, len(wa) - 1024):
        m = float((wa[off:off + 1024] == ra).mean())
        if m > best[1]:
            best = (off, m)
    return best


CFG = {'本机': ours}
for k in ('capA', 'capB'):
    off, m = find_body(BODY[k], ours)
    CFG[k] = BODY[k][off:off + 1024]
    print(f"  {k} config body @0x{off:x}  与本机相同率 {100 * m:.1f}%")

o = np.frombuffer(CFG['本机'], np.uint8)
a = np.frombuffer(CFG['capA'], np.uint8)
b = np.frombuffer(CFG['capB'], np.uint8)
model_spec = (a == b) & (a != o)
ver_spec = (a != b)

print("\n" + "=" * 100)
print("### 1 机型相关字节（capA==capB 且 != 本机）")
print("=" * 100)
print(f"  机型相关 {int(model_spec.sum())}/1024；同型号两版之间也变 {int(ver_spec.sum())}/1024")
runs, i = [], 0
while i < 1024:
    if model_spec[i]:
        j = i
        while j < 1024 and model_spec[j]:
            j += 1
        runs.append((i, j - 1)); i = j
    else:
        i += 1
big = [r for r in runs if r[1] - r[0] >= 2]
print(f"  >=3 B 的机型相关连续段 {len(big)} 个（前 16）：")
for s, e in big[:16]:
    print(f"    +0x{s:03x}..+0x{e:03x} ({e - s + 1:>3} B)  本机 "
          f"{' '.join(f'{v:02x}' for v in o[s:e + 1][:10])}  |  capA "
          f"{' '.join(f'{v:02x}' for v in a[s:e + 1][:10])}")

print("\n" + "=" * 100)
print("### 2 自证锚点：libinput 硬数字在本机 config body 里的命中")
print("=" * 100)
for nm, v in (('压力满量程 2000', 2000), ('palm 600', 600), ('thumb 1000', 1000),
              ('X 物理 135', 135), ('Y 物理 80', 80), ('节点 25', 25), ('节点 16', 16),
              ('通道 32', 32), ('通道 27', 27)):
    be = v.to_bytes(2, 'big'); le = v.to_bytes(2, 'little')
    hb = [i for i in range(1023) if ours[i:i + 2] == be]
    hl = [i for i in range(1023) if ours[i:i + 2] == le]
    h8 = [i for i in range(1024) if v < 256 and ours[i] == v]
    print(f"  {nm:<16} u16BE@{[hex(x) for x in hb]}  u16LE@{[hex(x) for x in hl]}"
          f"  单字节@{[hex(x) for x in h8[:10]]}")
print("  （u16 均匀期望 ~0.016 处）")

print("\n" + "=" * 100)
print("### 3 X/Y 分辨率候选：u16 对，比值 ~ 面板长宽比")
print("=" * 100)


def cands(cfg, ms, rlo, rhi, vmin=150, vmax=30000):
    out = []
    for en in ('big', 'little'):
        for i in range(0, 1022, 2):
            vx = int.from_bytes(cfg[i:i + 2], en)
            if not (vmin <= vx <= vmax):
                continue
            for j in range(0, 1022, 2):
                if i == j:
                    continue
                vy = int.from_bytes(cfg[j:j + 2], en)
                if not (vmin <= vy <= vmax):
                    continue
                r = vx / vy
                if rlo <= r <= rhi:
                    out.append((bool(ms[i:i + 2].any() or ms[j:j + 2].any()), en, i, j, vx, vy, r))
    return out


for tag in ('本机', 'capA'):
    r = cands(CFG[tag], model_spec, 1.50, 1.90)
    r.sort(key=lambda t: (not t[0], abs(t[6] - 1.6875)))
    print(f"\n  --- {tag}（比值 1.50-1.90）---")
    for ms, en, i, j, vx, vy, rr in r[:12]:
        print(f"    {'★机型相关' if ms else '          '}  {'BE' if en=='big' else 'LE'}  X@+0x{i:03x}={vx:<6} "
              f"Y@+0x{j:03x}={vy:<6} 比值 {rr:.4f}")

print("\n" + "=" * 100)
print("### 4 本机 config body 全文（32 行 x 32 B）")
print("=" * 100)
for r0 in range(0, 1024, 32):
    row = ours[r0:r0 + 32]
    asc = "".join(chr(c) if 32 <= c < 127 else "." for c in row)
    print(f"  +0x{r0:03x}  " + " ".join(f"{c:02x}" for c in row) + f"  |{asc}|")
