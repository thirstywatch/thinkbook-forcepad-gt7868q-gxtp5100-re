# -*- coding: utf-8 -*-
"""加密载荷审计 第三轮 —— 用声明边界重测，并找低熵区/常量区（有没有"没加密的部分"）。
只读本机文件。"""
import io, os, collections, math

BIN = r'C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN'
HDR = bytes.fromhex('000188FA') + b'\x5f\x37' + b'YELSTO' + bytes.fromhex('000006') + b'7868Q'
PA_OFF, PA_LEN = 0x11BC, 100608          # 工区声明的载荷A
B_OFF = 0x19ABC                          # 明文段B 起点

out = []
def P(s=''):
    print(s); out.append(str(s))

d = open(BIN, 'rb').read()
hi = d.find(HDR)
P("容器 %d B" % len(d))
P("明文头位置 0x%X ; 声明载荷A 起点 0x%X ; 明文段B 起点 0x%X" % (hi, PA_OFF, B_OFF))
P("头与载荷A 之间: %d 字节（0x%X..0x%X）" % (PA_OFF - hi, hi, PA_OFF))
P("载荷A 末端 0x%X ; 到 B 之间还剩 %d 字节" % (PA_OFF + PA_LEN, B_OFF - (PA_OFF + PA_LEN)))
P()
P("=== 明文头 24B + 其后到 0x11BC 的 128 字节 ===")
seg = d[hi:PA_OFF]
for k in range(0, len(seg), 16):
    row = seg[k:k + 16]
    asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in row)
    P("  0x%04X  %s  |%s|" % (k, row.hex(' '), asc))
P()

A = d[PA_OFF:PA_OFF + PA_LEN]
P("载荷A = %d 字节  (16 整除=%s)" % (len(A), len(A) % 16 == 0))

def ent(b):
    if not b: return 0.0
    c = [0] * 256
    for x in b: c[x] += 1
    e = 0.0
    for v in c:
        if v:
            p = v / len(b); e -= p * math.log2(p)
    return e

P()
P("=" * 76)
P("① 熵分布（每 512 字节；加密区应 ~7.9，明文/填充区更低）")
P("=" * 76)
low = []
for k in range(0, len(A), 512):
    chunk = A[k:k + 512]
    if len(chunk) < 512: break
    e = ent(chunk)
    if e < 7.5:
        low.append((k, e))
P("   512B 块数 %d ; 熵<7.5 的块 %d 个" % (len(A) // 512, len(low)))
for k, e in low[:25]:
    P("     0x%05X  熵 %.2f" % (k, e))
if len(low) > 25:
    P("     … 另 %d 个" % (len(low) - 25))
P()

P("=" * 76)
P("② 常量字节游程（≥16 字节同值）—— 典型的未加密填充")
P("=" * 76)
runs = []
k = 0
while k < len(A):
    j = k
    while j + 1 < len(A) and A[j + 1] == A[k]:
        j += 1
    if j - k + 1 >= 16:
        runs.append((k, j - k + 1, A[k]))
    k = j + 1
P("   共 %d 段；最长 12 段：" % len(runs))
for off, ln, val in sorted(runs, key=lambda x: -x[1])[:12]:
    P("     偏移 0x%05X  长 %5d  值 0x%02X" % (off, ln, val))
P()

P("=" * 76)
P("③ 用声明边界重测：自相关")
P("=" * 76)
ct = A[24:] if A[:24] == HDR else A
P("   （载荷A 起始 24B 与已知明文头一致 = %s；以下对整体 %d B 计算）" % (A[:24] == HDR, len(A)))
for lag in (16, 64, 256, 1024, 1084, 2048, 4096, 8192, 16384, 32768, 65536):
    if lag >= len(A): continue
    n = len(A) - lag
    idz = range(0, n, 7)
    t = 0; m = 0
    for k in idz:
        t += 1
        if A[k] == A[k + lag]: m += 1
    P("   lag %6d : %5.2f%%" % (lag, 100.0 * m / t))
P()

P("=" * 76)
P("④ 用声明边界重测：重复块率 & 跨镜像共用")
P("=" * 76)
for n in (8, 16, 32):
    best = (0, 0, 0)
    for ph in range(n):
        bs = [A[ph + k * n: ph + (k + 1) * n] for k in range((len(A) - ph) // n)]
        c = collections.Counter(bs)
        dup = sum(v - 1 for v in c.values() if v > 1)
        if dup > best[1]: best = (ph, dup, len(bs))
    ph, dup, tot = best
    P("   %2d B 块: 最佳相位 %2d  重复 %5d/%5d = %5.2f%%" % (n, ph, dup, tot, 100.0 * dup / tot))
caps = [
    ("Cap 22001E0D", r'<WORKSPACE>'),
    ("Cap 26002816", r'<WORKSPACE>'),
]
bufs = {}
for nm, cp in caps:
    if os.path.exists(cp): bufs[nm] = open(cp, 'rb').read()
for nm, o in bufs.items():
    tot = 0; hit = 0
    for k in range(0, len(A) - 16, 16 * 53):
        tot += 1
        if o.find(A[k:k + 16]) >= 0: hit += 1
    P("   %-14s 抽样 %4d 块 → 命中 %4d = %5.1f%%" % (nm, tot, hit, 100.0 * hit / tot))
P()

o = r'<LAB>\touchpad-lab\re\aes_payload_audit3_out.txt'
io.open(o, 'w', encoding='utf-8').write('\n'.join(out))
print("[已写] " + o)
