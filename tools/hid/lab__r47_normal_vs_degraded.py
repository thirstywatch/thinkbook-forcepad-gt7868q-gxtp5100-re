#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""lab__r47_normal_vs_degraded.py — ★ 决定性对照：重启后(正常态) vs 退化态
（同一天、同一版本；唯一变量 = 是否进过 bootloader）
（注意：Python 字符串里不要出现中文引号）"""
import sys, os, time, json, re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
LOGS = os.path.join(HERE, '..', '..', 'data', 'logs')
import gxmem

BASE = 0x4000
TOT = 0x8000
OUT = os.path.join(LOGS, 'gxt__normal_state_20261011.bin')
FAILD = os.path.join(LOGS, 'gxt__normal_failmap.json')

g = gxmem.Gx()
assert g.open(), "open fail"


def rd(a, n, tries=6):
    for _ in range(tries):
        d, _ = g.read(a, n)
        if d and len(d) >= n:
            return bytes(d[:n])
        time.sleep(0.1)
    return None


try:
    print("=== 正常态 dump（重启后）64B 步进 + 重试 ===")
    good = {}; bad = []
    t0 = time.time()
    for addr in range(BASE, BASE + TOT, 64):
        d = rd(addr, 64)
        if d is None:
            bad.append(addr)
        else:
            good[addr] = d
    print("  成功 %d / 失败 %d  耗时 %.0fs" % (len(good), len(bad), time.time() - t0))
    if bad:
        print("  失败: %s" % [hex(x) for x in bad[:20]])
    buf = bytearray(TOT)
    for a, d in good.items():
        buf[a - BASE:a - BASE + 64] = d
    open(OUT, 'wb').write(bytes(buf))
    json.dump({'base': BASE, 'tot': TOT, 'bad': bad}, open(FAILD, 'w'))
    print("  已保存 %s" % os.path.basename(OUT))
finally:
    g.close()

# ── 对比 ──
degr = open(os.path.join(LOGS, 'gxt__degraded_state_v2_20261011.bin'), 'rb').read()
dfail = set(json.load(open(os.path.join(LOGS, 'gxt__degraded_failmap.json')))['bad'])
nfail = set(json.load(open(FAILD))['bad'])

print()
print("=" * 80)
print("★★★ 决定性对照：正常态(现在) vs 退化态(本轮) —— 同版本、单变量")
print("=" * 80)
print()
print("=== ① 关键区逐字节 ===")
for a in (0x4000, 0x4008, 0x4010, 0x4018, 0x4020, 0x4028, 0x4030):
    off = a - BASE
    n = " ".join("%02X" % buf[off + i] for i in range(8))
    d = " ".join("%02X" % degr[off + i] for i in range(8))
    mark = "  ★不同" if n != d else "  = "
    print("  0x%04X  正常: %-24s  退化: %-24s%s" % (a, n, d, mark))

print()
print("=== ② 全 32 KB 差异统计（排除双方失败块）===")
tot = 0; dif = 0; runs = []
alle = []
for off in range(0, TOT):
    a = BASE + off
    if (a - a % 64) in dfail or (a - a % 64) in nfail:
        continue
    tot += 1
    if buf[off] != degr[off]:
        dif += 1
        alle.append((a, degr[off], buf[off]))
print("  可比字节 %d ；不同 %d (%.2f%%)" % (tot, dif, dif / tot * 100))
print()
print("=== ③ 差异连续段（top 20）===")
if alle:
    st = alle[0][0]; pv = alle[0][0]; items = [alle[0]]
    for x in alle[1:]:
        if x[0] == pv + 1:
            pv = x[0]; items.append(x)
        else:
            runs.append((st, pv, items)); st = x[0]; pv = x[0]; items = [x]
    runs.append((st, pv, items))
    for s, e, it in sorted(runs, key=lambda r: -(r[1] - r[0]))[:20]:
        print("  0x%04X-0x%04X (%3d B)  退化->正常: %s"
              % (s, e, e - s + 1,
                 " ".join("%02X->%02X" % (v, w) for _, v, w in it[:8])))
    print()
    print("  差异连续段总数 %d" % len(runs))

print()
print("=== ④ 逐 256B 块差异（只列有差异的）===")
for off in range(0, TOT, 256):
    a = BASE + off
    if (a - a % 64) in dfail or (a - a % 64) in nfail:
        continue
    n = sum(1 for i in range(256)
            if (a + i - (a + i) % 64) not in dfail
            and (a + i - (a + i) % 64) not in nfail
            and buf[off + i] != degr[off + i])
    if n:
        print("  0x%04X  %3d/256" % (a, n))
