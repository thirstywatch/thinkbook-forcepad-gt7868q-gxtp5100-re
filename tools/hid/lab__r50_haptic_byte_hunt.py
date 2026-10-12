#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""lab__r50_haptic_byte_hunt.py — 找"震动开关字节"
  ① 补 dump 0x0000-0x4000（此前从未读过）
  ② 重 dump 当前（退化态）0x4000-0xC000
  ③ 与正常态 dump 对比，列出【候选开关字节】
（Python 字符串里不要出现中文引号）"""
import sys, os, time, json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
LOGS = os.path.join(HERE, '..', '..', 'data', 'logs')
import gxmem

g = gxmem.Gx()
assert g.open(), "open fail"


def rd(a, n, tries=6):
    for _ in range(tries):
        d, _ = g.read(a, n)
        if d and len(d) >= n:
            return bytes(d[:n])
        time.sleep(0.1)
    return None


def dump_range(base, tot, tag):
    good = {}; bad = []
    t0 = time.time()
    for addr in range(base, base + tot, 64):
        d = rd(addr, 64)
        if d is None:
            bad.append(addr)
        else:
            good[addr] = d
    print("  [%s] 0x%04X-0x%04X  成功 %d / 失败 %d  (%.0fs)"
          % (tag, base, base + tot, len(good), len(bad), time.time() - t0))
    if bad:
        print("     失败: %s" % [hex(x) for x in bad[:12]])
    buf = bytearray(tot)
    for a, d in good.items():
        buf[a - base:a - base + 64] = d
    return bytes(buf), bad


try:
    print("=== ① 补 dump 0x0000-0x4000（项目此前未读过）===")
    low, lowbad = dump_range(0x0000, 0x4000, 'low')
    open(os.path.join(LOGS, 'gxt__now_low_20261011.bin'), 'wb').write(low)
    json.dump({'bad': lowbad}, open(os.path.join(LOGS, 'gxt__now_low_failmap.json'), 'w'))

    print()
    print("=== ② 重 dump 当前（退化态）0x4000-0xC000 ===")
    high, highbad = dump_range(0x4000, 0x8000, 'high')
    open(os.path.join(LOGS, 'gxt__now_high_20261011.bin'), 'wb').write(high)
    json.dump({'bad': highbad}, open(os.path.join(LOGS, 'gxt__now_high_failmap.json'), 'w'))
finally:
    g.close()

# ── ③ 分析 ──
print()
print("=" * 80)
print("=== ③ 0x0000-0x3FFF 概览（项目说是'未映射全零'，核实）===")
nz = [(i, low[i]) for i in range(len(low)) if low[i] != 0]
print("  非零字节数: %d / %d" % (len(nz), len(low)))
if nz:
    print("  非零区段（前 30）：")
    runs = []
    st = nz[0][0]; pv = nz[0][0]
    for a, _ in nz[1:]:
        if a == pv + 1:
            pv = a
        else:
            runs.append((st, pv)); st = a; pv = a
    runs.append((st, pv))
    for s, e in sorted(runs, key=lambda r: -(r[1] - r[0]))[:30]:
        print("    0x%04X-0x%04X (%4d B)  %s"
              % (s, e, e - s + 1, low[s:min(s + 12, e + 1)].hex(' ').upper()))
    print("  连续非零段总数 %d" % len(runs))

print()
print("=" * 80)
print("=== ④ 正常态 vs 当前(退化态) —— 找【候选开关字节】===")
NORM = open(os.path.join(LOGS, 'gxt__normal_state_20261011.bin'), 'rb').read()
nfail = set(json.load(open(os.path.join(LOGS, 'gxt__normal_failmap.json')))['bad'])
nhigh = {a: NORM[a - 0x4000:a - 0x4000 + 64] for a in range(0x4000, 0x4000 + 0x8000, 64)
         if a not in nfail}

# 关键：找【正常非零 → 当前为零】的字节（关掉的特征）
off_sig = []
for a in range(0x4000, 0x4000 + 0x8000):
    blk = a - a % 64
    if blk in nfail or blk in highbad:
        continue
    vn = NORM[a - 0x4000]; vc = high[a - 0x4000]
    if vn != 0 and vc == 0:
        off_sig.append((a, vn))
print("  『正常非零 -> 当前为 0』的字节数: %d" % len(off_sig))
if off_sig:
    runs = []
    st = off_sig[0][0]; pv = off_sig[0][0]; it = [off_sig[0]]
    for x in off_sig[1:]:
        if x[0] == pv + 1:
            pv = x[0]; it.append(x)
        else:
            runs.append((st, pv, it)); st = x[0]; pv = x[0]; it = [x]
    runs.append((st, pv, it))
    print("  连续段（top 25）：")
    for s, e, ii in sorted(runs, key=lambda r: -(r[1] - r[0]))[:25]:
        print("    0x%04X-0x%04X (%3d B)  原值: %s"
              % (s, e, e - s + 1, " ".join("%02X" % v for _, v in ii[:10])))

print()
print("=== ⑤ 项目记载的触觉相关地址，当前值 vs 正常值 ===")
for a, label in [(0x1800, '触觉参数区 27B(官方cfg布局)'),
                 (0x3800, '触觉参数区 8B(官方cfg布局)'),
                 (0x2000, '配置块A'), (0x2C00, '配置块B'),
                 (0x5F20, '压力帧按压状态'), (0x5F21, '压力帧状态字节')]:
    if 0x4000 <= a < 0xC000:
        vc = high[a - 0x4000]; vn = NORM[a - 0x4000]
        print("  0x%04X %-24s 正常 %02X  当前 %02X  %s"
              % (a, label, vn, vc, "★不同" if vn != vc else ""))
    elif a < 0x4000:
        vc = low[a]
        print("  0x%04X %-24s 当前 %02X  (在 0x0000-0x3FFF，无正常态对照)" % (a, label, vc))
