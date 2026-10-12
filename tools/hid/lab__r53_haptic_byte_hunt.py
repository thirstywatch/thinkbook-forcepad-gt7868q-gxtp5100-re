#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""lab__r53_haptic_byte_hunt.py —— 找'操控震动的字节'（阶段一：只读勘测）

思路（本轮新的、可执行的）：
  A. 设备活体 0x96F8 区 = 项目此前保存过的 'cfg 记录 1084 B'（前 32 B 逐字节对应）
     参考件：data/reference/lab__cfg_record_orig_1084.bin（2026-10-05 保存，健康态）
     ⇒ 直接做【活的 vs 参考】逐字节差分
  B. 稳定性检验：连读 3 次，看哪些字节在"自己变"（滚动计数/噪声）⇒ 先排除
  C. 三个"可写区"（0x1C00 / 0x4000 / 0x5F00）与健康快照对比
  D. 在整片设备内存里搜 sid cfg 触觉区（TAG 0x5C 时长阶梯 / 0x5D 强度档 / 0x75 微调表）的字节签名

★ 全程只读，不写任何字节。
(Python 字符串里不要出现中文引号)
"""
import sys, os, time, json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.join(HERE, '..', '..')
LOGS = os.path.join(ROOT, 'data', 'logs')
REF = os.path.join(ROOT, 'data', 'reference')
import gxmem

CFG = 0x96F8
CFGLEN = 1084


def hx(b):
    return " ".join("%02X" % x for x in b)


def rd(g, a, n, tries=10):
    for _ in range(tries):
        d, _ = g.read(a, n)
        if d and len(d) >= n:
            return bytes(d[:n])
        time.sleep(0.12)
    return None


g = gxmem.Gx()
if not g.open():
    print("Col04 open FAIL")
    raise SystemExit(3)

print("=" * 84)
print("A) 设备活体 0x96F8 区（%d B）vs 参考件 lab__cfg_record_orig_1084.bin" % CFGLEN)
print("=" * 84)

ref = open(os.path.join(REF, 'lab__cfg_record_orig_1084.bin'), 'rb').read()
print("  参考件长度 %d" % len(ref))

# 分 64 B 读
live = bytearray()
bad = []
for off in range(0, CFGLEN, 64):
    n = min(64, CFGLEN - off)
    d = rd(g, CFG + off, n)
    if d is None:
        bad.append(off)
        live += b'\x00' * n
    else:
        live += d
live = bytes(live)
print("  活体读取：失败块 %d 个 %s" % (len(bad), [hex(CFG + b) for b in bad[:8]]))
print()
print("  地址      参考(健康)                          活的(当前)                           同否")
for off in range(0, CFGLEN, 16):
    r = ref[off:off + 16]
    l = live[off:off + 16]
    if len(r) < 16:
        break
    mark = "" if r == l else "  ★异"
    print("  +0x%04X  %-32s  %-32s%s" % (off, hx(r), hx(l), mark))

diffs = [i for i in range(CFGLEN) if ref[i] != live[i]]
print()
print("  ⇒ 差异字节数：%d / %d" % (len(diffs), CFGLEN))
if diffs:
    print("  ⇒ 差异明细（前 60）:")
    for i in diffs[:60]:
        print("       +0x%04X (绝对 0x%04X):  参考 %02X  ->  活的 %02X" % (i, CFG + i, ref[i], live[i]))
    if len(diffs) > 60:
        print("       ... 还有 %d 个" % (len(diffs) - 60))
    # 连续段
    runs = []
    st = diffs[0]; pv = diffs[0]
    for x in diffs[1:]:
        if x == pv + 1:
            pv = x
        else:
            runs.append((st, pv)); st = x; pv = x
    runs.append((st, pv))
    print("  ⇒ 差异连续段: %s" % ", ".join("+0x%04X-0x%04X(%d)" % (s, e, e - s + 1) for s, e in runs[:20]))

json.dump({"live": live.hex(), "ref": ref.hex(), "diff": diffs},
          open(os.path.join(LOGS, 'gxt__r53_cfg_live.json'), 'w'))

print()
print("=" * 84)
print("B) 稳定性检验：连读 3 次 0x96F8 前 64 B")
print("=" * 84)
snaps = []
for k in range(3):
    d = rd(g, CFG, 64)
    snaps.append(d)
    print("  #%d  %s" % (k + 1, hx(d) if d else "<FAIL>"))
    time.sleep(0.5)
for i in range(64):
    vals = set(s[i] for s in snaps if s)
    if len(vals) > 1:
        print("    ★ +0x%04X 在三次读之间自己变了: %s" % (i, [("%02X" % s[i]) for s in snaps if s]))

print()
print("=" * 84)
print("C) 三个可写区 + 两个只读触觉区：当前 vs 健康快照(15:01)")
print("=" * 84)
NORM = open(os.path.join(LOGS, 'gxt__normal_state_20261011.bin'), 'rb').read()
CUR = open(os.path.join(LOGS, 'gxt__now_high_20261011.bin'), 'rb').read()
for base, ln, nm in [(0x1800, 0x20, '0x1800 触觉参数区(只读)'),
                     (0x1C00, 0x40, '0x1C00 可写区'),
                     (0x2800, 0x20, '0x2800'),
                     (0x3800, 0x20, '0x3800 触觉参数区(只读)'),
                     (0x4000, 0x40, '0x4000 固件头(可写)'),
                     (0x5F00, 0x40, '0x5F00 可写区')]:
    print("  ── %s ──" % nm)
    for i in range(0, ln, 16):
        vn = NORM[base - 0x4000 + i: base - 0x4000 + i + 16]
        vc = CUR[base - 0x4000 + i: base - 0x4000 + i + 16]
        mark = "" if vn == vc else "  ★异"
        print("    0x%04X  健康 %-32s  当前 %-32s%s" % (base + i, hx(vn), hx(vc), mark))

print()
print("=" * 84)
print("D) 在设备内存里搜 sid cfg 触觉区签名（TAG 0x5C/0x5D/0x75）")
print("=" * 84)

SID0 = os.path.join(REF, 'gxt__tpcfgsid0_Xiaomi7867_20240307.cfg.txt')
raw = bytes(int(x, 16) for x in open(SID0).read().replace('\n', '').split(',') if x.strip())
print("  sid0 cfg 长度 %d" % len(raw))
# 提取各 TAG 的 payload 作为签名
sigs = {}
i = 64  # 64 B 头
while i + 4 <= len(raw):
    ln = raw[i]
    tag = raw[i + 1]
    if tag in (0x5C, 0x5D, 0x75, 0x77, 0x78, 0x7A):
        sigs.setdefault(tag, raw[i + 2:i + 2 + ln])
    i += 2 + ln
for t in sorted(sigs):
    p = sigs[t]
    print("  TAG 0x%02X  len=%d  payload=%s" % (t, len(p), hx(p[:24])))

whole = bytearray(CUR)
whole += bytearray(NORM)
mem = bytes(whole)
for t in sorted(sigs):
    p = sigs[t]
    if len(p) < 8:
        continue
    hits = []
    pos = mem.find(p)
    while pos >= 0:
        hits.append(pos)
        pos = mem.find(p, pos + 1)
    # 也搜前 16 字节的子串
    if not hits and len(p) >= 16:
        sub = p[:16]
        pos = mem.find(sub)
        while pos >= 0:
            hits.append(pos)
            pos = mem.find(sub, pos + 1)
        lbl = "(前16B)"
    else:
        lbl = ""
    print("  → TAG 0x%02X %s 完整签到命中 %d 处  %s"
          % (t, lbl, len(hits), [hex(h) for h in hits[:8]]))

g.close()
print()
print("完成。")
