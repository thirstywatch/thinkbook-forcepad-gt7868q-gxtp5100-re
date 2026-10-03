# -*- coding: utf-8 -*-
"""tpcfgsid*.cfg（sid0/sid2/sid3）文件头 + TLV 全表 + 与配置体的跨文件对齐"""
import os, struct, collections, random, math

BASE = r"<WORKSPACE>"
FILES = {"sid0": "sid0.bin", "sid2": "sid2.bin", "sid3": "sid3.bin"}

def H(b):
    if not b: return 0.0
    c = collections.Counter(b); n = len(b)
    return -sum(v/n*math.log2(v/n) for v in c.values())

def hd(b, base=0, n=None, step=16):
    out = []
    n = len(b) if n is None else min(n, len(b))
    for i in range(0, n, step):
        chunk = b[i:i+step]
        out.append("  +%04X  %-47s  %s" % (base+i, " ".join("%02x" % c for c in chunk),
                    "".join(chr(c) if 32 <= c < 127 else '.' for c in chunk)))
    return "\n".join(out)

def parse_header(d):
    """列出前 0x60 字节的字段假设"""
    print("  长度 = %d B   H0 = %.4f" % (len(d), H(d)))
    print(hd(d, 0, 0x60))
    vid = d[0:8].rstrip(b'\0'); pid = d[8:16].rstrip(b'\0')
    rev = struct.unpack_from('<I', d, 16)[0]
    proj = d[20:28].rstrip(b'\0')
    cfgv = struct.unpack_from('<H', d, 28)[0]
    ts = struct.unpack_from('<I', d, 30)[0]
    print("  vid=%r pid=%r rev=%d project=%r cfg_ver=%d ts=0x%08X(%d)" %
          (vid, pid, rev, proj, cfgv, ts, ts))
    import datetime
    try:
        print("  ts -> %s UTC" % datetime.datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S'))
    except Exception as e:
        print("  ts -> %s" % e)
    # 找 ASCII 日期串
    for i in range(0x1C, 0x40):
        if d[i:i+8].isdigit():
            print("  日期串 @0x%02X = %r ; 其前一字节 @0x%02X = 0x%02X" % (i, d[i:i+8].decode(), i-1, d[i-1]))
    # 找 body 起点：第一个 0xD6/0x04 之类
    z = 0
    for i in range(0x2b, 0x60):
        if d[i] == 0:
            z += 1
        else:
            break
    print("  0x2B 起连续零 = %d 个 ⇒ 首个非零 @0x%02X = 0x%02X" % (z, 0x2b+z, d[0x2b+z]))
    return vid, pid, rev, proj, cfgv, ts

def walk(buf, start=0):
    i = start; out = []
    while i < len(buf) - 1:
        tag = buf[i]; ln = buf[i+1]
        if i + 2 + ln > len(buf):
            out.append((i, tag, ln, None)); break
        out.append((i, tag, ln, buf[i+2:i+2+ln])); i += 2 + ln
    return out

def cov(buf, start=0):
    w = walk(buf, start)
    used = sum(2 + (0 if x[3] is None else x[2]) for x in w)
    return used, len(w), w

def describe(pl):
    kind = []
    if pl is None: return "TRUNC"
    vals = list(pl)
    if len(vals) >= 3 and all(0x20 <= v < 0x7f for v in vals): kind.append("ASCII")
    if len(vals) >= 4 and all(v not in (0, 0xff) for v in vals):
        if all(vals[i] <= vals[i+1] for i in range(len(vals)-1)): kind.append("单调↑")
        if all(vals[i] >= vals[i+1] for i in range(len(vals)-1)): kind.append("单调↓")
    if len(pl) % 2 == 0 and pl:
        for e in ('little', 'big'):
            v = [int.from_bytes(pl[i:i+2], e) for i in range(0, len(pl), 2)]
            if all(x < 65536 for x in v) and max(v) > 1:
                s = "%s16" % ("LE" if e == 'little' else "BE")
                if all(0 < x < 4096 for x in v): kind.append(s + "小值")
                if len(v) >= 4 and max(v) > 1000: kind.append(s + "大值")
                break
    if len(set(vals)) == 1 and len(vals) > 2: kind.append("常量")
    return "/".join(kind) or "-"

def main():
    datas = {}
    for k, fn in FILES.items():
        p = os.path.join(BASE, fn)
        if not os.path.exists(p):
            print("!! 缺 %s" % p); continue
        datas[k] = open(p, 'rb').read()
    for k in ("sid0", "sid2", "sid3"):
        if k not in datas: continue
        print("=" * 78)
        print("### %s (%s)" % (k, FILES[k]))
        parse_header(datas[k])

    # body 起点扫描：找一个起点使 TLV 覆盖率显著高于打乱对照
    print()
    print("=" * 78)
    print("### TLV 起点扫描（各 cfg）")
    for k in ("sid0", "sid2", "sid3"):
        if k not in datas: continue
        d = datas[k]
        best = None
        for st in list(range(0x20, 0x60)):
            used, n, w = cov(d, st)
            r = used / len(d)
            rs = []
            for _ in range(30):
                y = bytearray(d); random.shuffle(y)
                rs.append(cov(bytes(y), st)[0] / len(d))
            rm = sum(rs)/len(rs)
            if best is None or r - rm > best[3]:
                best = (st, r, rm, r - rm)
        print("  %s: 最优起点 0x%02X  覆盖 %.1f%%  打乱对照 %.1f%%  Δ=%.1f pt" %
              (k, best[0], best[1]*100, best[2]*100, best[3]*100))

    # 全表
    starts = {"sid0": 0x37, "sid2": None, "sid3": None}
    for k in ("sid0", "sid2", "sid3"):
        if k not in datas: continue
        d = datas[k]
        best = None
        for st in range(0x20, 0x60):
            used, n, w = cov(d, st)
            r = used/len(d)
            rs = []
            for _ in range(30):
                y = bytearray(d); random.shuffle(y)
                rs.append(cov(bytes(y), st)[0]/len(d))
            rm = sum(rs)/len(rs)
            if best is None or r-rm > best[3]: best = (st, r, rm, r-rm)
        st = best[0]
        print()
        print("=" * 78)
        print("### %s TLV 全表（起点 0x%02X，覆盖 %.1f%%）" % (k, st, best[1]*100))
        print("%-7s %-5s %-5s %-14s %s" % ("偏移", "TAG", "LEN", "类型", "payload"))
        used, n, w = cov(d, st)
        for off, tag, ln, pl in w:
            if pl is None:
                print("%-7s 0x%02X  %-5d %-14s <TRUNC>" % (hex(off), tag, ln, "")); continue
            s = pl[:24].hex(' ')
            if len(pl) > 24: s += " …"
            print("%-7s 0x%02X  %-5d %-14s %s" % (hex(off), tag, ln, describe(pl), s))

main()
