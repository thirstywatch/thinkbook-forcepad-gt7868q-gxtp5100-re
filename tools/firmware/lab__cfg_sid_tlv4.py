# -*- coding: utf-8 -*-
"""tpcfgsid*.cfg 定案解析：64 B 头(0x3B=u16LE TLV长度) + 0x40 起 [LEN u8][TAG u8][payload]"""
import os, collections, struct, datetime, random

BASE = r"<WORKSPACE>"
FILES = [("sid0", "sid0.bin"), ("sid2", "sid2.bin"), ("sid3", "sid3.bin")]

def walk(d, st):
    i = st; out = []
    while i + 2 <= len(d):
        ln = d[i]; tag = d[i+1]
        if ln < 2 or i + ln > len(d):
            out.append((i, tag, ln, None)); break
        out.append((i, tag, ln, d[i+2:i+ln])); i += ln
    return out

print("=" * 78)
print("### 头部定案（64 B，0x00-0x3F）")
print("%-6s %-8s %-8s %-5s %-9s %-4s %-11s %-11s %-6s %-8s" %
      ("文件", "vid", "pid", "rev", "project", "cfgv", "ts(LEx32)", "日期串", "0x3B", "@0x3D", ))
for name, fn in FILES:
    d = open(os.path.join(BASE, fn), 'rb').read()
    vid = d[0:8].rstrip(b'\0').decode('latin1'); pid = d[8:16].rstrip(b'\0').decode('latin1')
    rev = struct.unpack_from('<I', d, 16)[0]
    proj = d[20:28].rstrip(b'\0').decode('latin1')
    cfgv = struct.unpack_from('<H', d, 28)[0]
    ts = struct.unpack_from('<I', d, 30)[0]
    ds = d[0x23:0x2B].decode('latin1')
    tlvlen = struct.unpack_from('<H', d, 0x3B)[0]
    print("%-6s %-8s %-8s %-5d %-9s %-4d %-11d %-11s 0x%02X=%-5d %s  (len=%d, 0x40+%d=%d %s)" %
          (name, vid, pid, rev & 0xff, proj, cfgv, ts, ds, d[0x3B], tlvlen,
           d[0x3D:0x40].hex(' '), len(d), tlvlen, 0x40 + tlvlen,
           "✓到文件尾" if 0x40 + tlvlen == len(d) else "✗"))

for name, fn in FILES:
    d = open(os.path.join(BASE, fn), 'rb').read()
    w = walk(d, 0x40)
    used = sum(x[2] if x[3] is not None else 0 for x in w)
    tags = [x[1] for x in w if x[3] is not None]
    asc = sum(1 for a, b in zip(tags, tags[1:]) if b > a) / max(1, len(tags)-1)
    print()
    print("=" * 78)
    print("### %s TLV（起点 0x40）：块数 %d  覆盖 %.1f%%  末尾@0x%X  TAG严格递增比 %.2f"
          % (name, len(w), used/len(d)*100, w[-1][0] + (w[-1][2] if w[-1][3] is not None else 0), asc))
    if name != "sid0":
        continue
    print("%-7s %-5s %-5s %-6s %-10s %s" % ("偏移", "LEN", "TAG", "paylen", "类型", "payload"))
    for off, tag, ln, pl in w:
        if pl is None:
            print("%-7s 0x%02X  0x%02X  %-6s %-10s <TRUNC>" % (hex(off), ln, tag, "", "")); continue
        vals = list(pl); kind = []
        if len(vals) >= 3 and all(0x20 <= v < 0x7f for v in vals): kind.append("ASCII")
        if len(vals) >= 4 and all(v not in (0, 0xff) for v in vals):
            if all(vals[i] <= vals[i+1] for i in range(len(vals)-1)): kind.append("单调↑")
            if all(vals[i] >= vals[i+1] for i in range(len(vals)-1)): kind.append("单调↓")
        if len(vals) % 2 == 0 and vals:
            v = [int.from_bytes(pl[i:i+2], 'little') for i in range(0, len(pl), 2)]
            if max(v) > 0: kind.append("LE16max=%d" % max(v))
            v = [int.from_bytes(pl[i:i+2], 'big') for i in range(0, len(pl), 2)]
            if max(v) > 0: kind.append("BE16max=%d" % max(v))
        if len(set(vals)) == 1 and len(vals) > 2: kind.append("常量0x%02X" % vals[0])
        s = pl[:28].hex(' ')
        if len(pl) > 28: s += " …"
        print("%-7s 0x%02X  0x%02X  %-6d %-10s %s" % (hex(off), ln, tag, len(pl), ",".join(kind) or "-", s))
