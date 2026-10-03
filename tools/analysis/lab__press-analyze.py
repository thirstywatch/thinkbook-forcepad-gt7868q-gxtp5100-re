#!/usr/bin/env python3
"""press-analyze.py —— 从 press-log.txt 客观测定点击阈值（报文级，不靠手感）

报文格式（REPORT-LAYOUT.md）：
  data[0]    报文ID (0x04)
  data[1]    低4位=按键位 / 高4位=触点ID
  data[2..3] X (LE16)
  data[4..5] Y (LE16)
  data[6..7] 压力 (LE16, 0..2000)
  data[36..37] 扫描时间
  data[39].bit0 按下位
判据：byte39.bit0 从 0→1 那一刻的压力 = 按下阈值；1→0 = 松手阈值。
基线（2026-09-13 实测）：按下中位 143（140..147）/ 松手中位 94（88..99）
用法： python press-analyze.py [press-log.txt]
"""
import re, sys, statistics as st, os

p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'poc', 'press-log.txt')
pat = re.compile(r'data=\s*((?:[0-9A-F]{2}\s*){40})')
rows = []
for ln in open(p, encoding='utf-8', errors='ignore'):
    m = pat.search(ln)
    if not m:
        continue
    b = [int(x, 16) for x in m.group(1).split()]
    if len(b) != 40:
        continue
    rows.append((b[6] | (b[7] << 8), b[39] & 1))

print(f"文件: {p}")
print(f"解析到 {len(rows)} 条 40 字节报文")
if not rows:
    sys.exit(1)
press = [x for x, _ in rows]
print(f"压力范围 {min(press)} .. {max(press)}")
up = [x for x, t in rows if t == 1]
dn = [x for x, t in rows if t == 0]
print(f"按下位=1: {len(up)} 条  压力 {min(up) if up else '-'}..{max(up) if up else '-'}")
print(f"按下位=0: {len(dn)} 条  压力 {min(dn) if dn else '-'}..{max(dn) if dn else '-'}")

prev, pe, re_ = None, [], []
for pr, t in rows:
    if prev is not None and t != prev:
        (pe if t == 1 else re_).append(pr)
    prev = t


def rep(name, v):
    if not v:
        print(f"  {name}: 无")
        return
    print(f"  {name}: n={len(v)}  最小={min(v)}  中位={st.median(v)}  最大={max(v)}")
    print(f"      全部={v[:40]}")


print("\n--- 跳变点 ---")
rep("0->1 【按下】时的压力", pe)
rep("1->0 【松手】时的压力", re_)

print("\n--- 判定 ---")
if pe:
    med = st.median(pe)
    if med < 100:
        print(f"  ★ 按下中位 = {med} < 100  ⇒ 【阈值已变低】写入生效")
    else:
        print(f"  按下中位 = {med}（基线 143）⇒ 未变")
else:
    print("  本段没有捕获到按下事件（采集期间请多按几次板子）")
