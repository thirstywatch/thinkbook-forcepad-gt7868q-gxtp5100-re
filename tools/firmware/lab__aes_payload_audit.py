# -*- coding: utf-8 -*-
"""加密载荷结构审计 —— 只读本机文件，不碰任何设备。

目的：
  ① 验工区那句「AES，16 字节块重复率 10.97%」到底成不成立
  ② 用「块相位扫描」找出真正的分组对齐（ECB 特征）—— CBC/CTR 下重复数应≈0
  ③ 把重复块映射出来：连续同块的游程 = 明文里的重复区（通常是大片 0x00/0xFF 填充）
  ④ 跨文件比对：这些密文块是否也出现在别的同族容器里（= 同密钥/同模式）
"""
import io, os, collections, random, math

BIN = r'C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN'
HDR = bytes.fromhex('000188FA') + b'\x5f\x37' + b'YELSTO' + bytes.fromhex('000006') + b'7868Q'
PL_LEN = 100608

out = []
def P(s=''):
    print(s)
    out.append(str(s))

d = open(BIN, 'rb').read()
P("容器: %s   %d 字节" % (os.path.basename(BIN), len(d)))
i = d.find(HDR)
P("明文头(24B) 位置: 0x%X" % i)
A = d[i:i + PL_LEN]
P("载荷A: 声明 %d / 实取 %d   头24B = %s" % (PL_LEN, len(A), A[:24].hex(' ')))
ct = A[24:]
P("密文: %d 字节   16 整除=%s   块数=%d" % (len(ct), len(ct) % 16 == 0, len(ct) // 16))
P()

def blocks_at(buf, phase, n=16):
    return [buf[phase + k * n: phase + (k + 1) * n]
            for k in range((len(buf) - phase) // n)]

def dup_stats(buf, phase, n=16):
    bs = blocks_at(buf, phase, n)
    c = collections.Counter(bs)
    dup = sum(v - 1 for v in c.values() if v > 1)
    return len(bs), len(c), dup, c

P("=" * 74)
P("① 块相位扫描（16 字节）—— 找真正的分组对齐")
P("   ECB ⇒ 正确相位重复数高；CBC/CTR ⇒ 所有相位都应≈0")
P("=" * 74)
best = None
for p in range(16):
    tot, nuniq, dup, c = dup_stats(ct, p)
    P("   phase %2d : 块 %5d  不同 %5d  重复 %4d  (%.2f%%)"
      % (p, tot, nuniq, dup, (dup / tot * 100) if tot else 0))
    if best is None or dup > best[2]:
        best = (p, tot, dup, c)
p, tot, dup, c = best
P("   ⇒ 最佳相位 = %d（重复 %d 块）" % (p, dup))
P()

P("=" * 74)
P("② 最重复的 16 字节块（相位 %d，前 12）" % p)
P("=" * 74)
for blk, cnt in c.most_common(12):
    if cnt < 2:
        break
    P("   %s  ×%d" % (blk.hex(' '), cnt))
P()

P("=" * 74)
P("③ 连续同块的游程（= 明文中成片的重复内容）")
P("=" * 74)
bs = blocks_at(ct, p)
runs, cur, n = [], bs[0], 1
for b in bs[1:]:
    if b == cur:
        n += 1
    else:
        if n >= 2:
            runs.append((cur, n))
        cur, n = b, 1
if n >= 2:
    runs.append((cur, n))
P("   游程(≥2) 共 %d 个；最长的 10 个：" % len(runs))
for blk, n2 in sorted(runs, key=lambda x: -x[1])[:10]:
    P("     ×%-5d %s" % (n2, blk.hex(' ')))
P()

P("=" * 74)
P("③b 最常见块的偏移与间距（间距=周期性结构的线索）")
P("=" * 74)
top_blk, top_cnt = c.most_common(1)[0]
offs = [k * 16 for k, b in enumerate(bs) if b == top_blk]
P("   最多块 %s 出现 %d 次；前 20 个偏移：" % (top_blk.hex(' '), top_cnt))
P("   " + ", ".join("0x%X" % o for o in offs[:20]))
deltas = collections.Counter(offs[k + 1] - offs[k] for k in range(len(offs) - 1))
P("   相邻间距直方图： " + ", ".join("%d×%d" % (dd, cc) for dd, cc in deltas.most_common(8)))
if len(offs) > 1:
    P("   首尾跨度: 0x%X .. 0x%X" % (offs[0], offs[-1]))
P()

P("=" * 74)
P("④ 对照：同长度随机数据")
P("=" * 74)
random.seed(1)
rnd = bytes(random.getrandbits(8) for _ in range(len(ct)))
_, _, rdup, _ = dup_stats(rnd, 0)
P("   随机 %d 字节 → 重复 %d 块（期望≈0）" % (len(rnd), rdup))
P()

P("=" * 74)
P("⑤ 全容器 / 各段的重复率（用来核对工区那个 10.97%）")
P("=" * 74)
segs = [("整个容器", 0, len(d)),
        ("载荷A 全部", i, i + PL_LEN),
        ("载荷A 密文", i + 24, i + PL_LEN),
        ("明文段B", 0x19ABC, len(d))]
for name, a, b in segs:
    if a >= b:
        continue
    buf = d[a:b]
    # 对每段自己找最佳相位
    bb = None
    for ph in range(16):
        t2, nu, dp, _ = dup_stats(buf, ph)
        if bb is None or dp > bb[1]:
            bb = (ph, dp, t2)
    ph, dp, t2 = bb
    P("   %-12s %8d B  最佳相位 %2d  重复 %5d  (%.2f%%)"
      % (name, len(buf), ph, dp, (dp / t2 * 100) if t2 else 0))
P()

P("=" * 74)
P("⑥ 跨文件：这些冒头密文块是否也出现在别的同族容器里")
P("=" * 74)
top = [b for b, cc in c.most_common(50) if cc >= 3]
P("   参与比对: 出现≥3次的块 %d 个" % len(top))
cands = [
    r'<LAB>\touchpad-lab\poc\pkg\gt7936l\GT7936L_16753412.bin',
    r'<WORKSPACE>',
    r'<WORKSPACE>',
]
for cp in cands:
    if not os.path.exists(cp):
        P("   [缺失] %s" % os.path.basename(cp))
        continue
    o = open(cp, 'rb').read()
    hit = sum(1 for b in top if o.find(b) >= 0)
    P("   %-46s %9d B   命中 %d/%d" % (os.path.basename(cp)[:46], len(o), hit, len(top)))
P()

P("=" * 74)
P("⑦ 头部 24 B 明文里是否含长度/算法线索")
P("=" * 74)
h = A[:24]
P("   原始: " + h.hex(' '))
P("   BE  u32@0  = 0x%08X" % int.from_bytes(h[0:4], 'big'))
P("   BE  u16@4  = 0x%04X" % int.from_bytes(h[4:6], 'big'))
P("   BE  u16@10 = 0x%04X   (紧邻 'YELSTO' 之后)" % int.from_bytes(h[10:12], 'big'))
P("   尾部 6B  = " + h[18:24].hex(' '))
P()

o = r'<LAB>\touchpad-lab\re\aes_payload_audit_out.txt'
io.open(o, 'w', encoding='utf-8').write('\n'.join(out))
print("[已写] " + o)
