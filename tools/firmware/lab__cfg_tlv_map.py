# -*- coding: utf-8 -*-
"""tpcfgsid*.cfg 逐字段还原：正确帧 [LEN][TAG] + 跨厂商 TAG 命名空间对照"""
import os, collections

CFG = r"<WORKSPACE>"
FILES = [("sid0", "sid0.bin", "Xiaomi 7867 2024-03-07"), ("sid3", "sid3.bin", "LaiBao 7986P 2022-07-01")]

def walk(d, st=0x40):
    i = st; out = []
    while i + 2 <= len(d):
        ln = d[i]; tag = d[i+1]
        if ln < 2 or i + ln > len(d):
            out.append((i, tag, ln, None)); break
        out.append((i, tag, ln, d[i+2:i+ln])); i += ln
    return out

data = {}
for name, fn, desc in FILES:
    d = open(os.path.join(CFG, fn), 'rb').read()
    w = [x for x in walk(d) if x[3] is not None]
    data[name] = (d, w, desc)
    print("%s: %d B  条目 %d  TAG 严格递增 %s" %
          (name, len(d), len(w), all(b[1] > a[1] for a, b in zip(w, w[1:]))))

s0 = {x[1]: x for x in data["sid0"][1]}
s3 = {x[1]: x for x in data["sid3"][1]}
alltags = sorted(set(s0) | set(s3))
print()
print("=" * 100)
print("### TAG 命名空间对照（sid0 = Xiaomi 7867 / sid3 = LaiBao 7986P）")
print("%-5s | %-4s %-5s | %-4s %-5s | %s" % ("TAG", "0的LEN", "paylen", "3的LEN", "paylen", "payload 前 20 B（sid0 / sid3）"))
print("-" * 100)
same_len = 0
for t in alltags:
    a = s0.get(t); b = s3.get(t)
    la = a[2] if a else None; lb = b[2] if b else None
    pa = a[3] if a else b''
    pb = b[3] if b else b''
    ident = (a is not None and b is not None and pa == pb)
    if a and b and la == lb: same_len += 1
    mark = "★同" if ident else ("≈同长" if (a and b and la == lb) else "")
    sa = pa[:20].hex(' '); sb = pb[:20].hex(' ')
    print("0x%02X | %-4s %-5s | %-4s %-5s | %-41s %-41s %s" %
          (t, la, len(pa), lb, len(pb), sa, sb if b else "", mark))
print("-" * 100)
print("共有 TAG %d ; 仅 sid0 %s ; 仅 sid3 %s ; 同 TAG 且同长 %d"
      % (len(set(s0) & set(s3)), [hex(x) for x in sorted(set(s0) - set(s3))],
         [hex(x) for x in sorted(set(s3) - set(s0))], same_len))

print()
print("=" * 100)
print("### 逐字节相同的 TAG（跨厂商逐字节相同 ⇒ 与机型无关的格式/常量）")
for t in alltags:
    a = s0.get(t); b = s3.get(t)
    if a and b and a[3] == b[3]:
        print("  TAG 0x%02X  paylen %d  %s" % (t, len(a[3]), a[3][:44].hex(' ')))

print()
print("=" * 100)
print("### 校准旧线结论：'子记录族 0x5C30/0x5D0C/0x5E0C/0x5F16' 与 '54 B 骨架'")
for t in (0x5A, 0x5C, 0x5D, 0x5E, 0x5F):
    for nm in ("sid0", "sid3"):
        dd, ww, _ = data[nm]
        m = [x for x in ww if x[1] == t]
        if m:
            off, tag, ln, pl = m[0]
            print("  %s TAG 0x%02X @文件偏移 0x%04X  条目前 4 B = %s （= LEN 0x%02X + TAG 0x%02X）"
                  % (nm, t, off, dd[off:off+4].hex(' '), ln, tag))
        else:
            print("  %s TAG 0x%02X 无" % (nm, t))
print()
print("  ⇒ 旧线看到的 `30 5c` / `0c 5d` / `0c 5e` / `16 5f` 就是 [LEN][TAG] 两个字节，不是'二级子标签'。")
