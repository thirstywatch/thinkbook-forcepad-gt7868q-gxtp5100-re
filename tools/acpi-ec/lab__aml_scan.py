#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aml_scan.py -- 最小 AML 扫描器：从 DSDT 原始表里把指定名字的
Method / Name / Scope 对象精确切出来（含宿主体字节与反汇编用的原始 hex）。

只做两件事：
  1) 线性扫描 NameOp(0x08) / MethodOp(0x14) / ScopeOp(0x10)，按 PkgLength 切片
  2) 对命中的对象输出：偏移、算出的包长、名字、参数个数、宿主体 hex、ASCII 串
不做语义反编译（那需要 iasl）。
"""
import sys, re

def pkglen(b, pos):
    """返回 (pkglen, header_bytes)。pos 指向 PkgLength 首字节。"""
    lead = b[pos]
    n = lead >> 6
    if n == 0:
        return (lead & 0x3F), 1
    if n == 1:
        return (lead & 0x0F) | (b[pos+1] << 4), 2
    if n == 2:
        return (lead & 0x0F) | (b[pos+1] << 4) | (b[pos+2] << 12), 3
    return (lead & 0x0F) | (b[pos+1] << 4) | (b[pos+2] << 12) | (b[pos+3] << 20), 4

NAME_CHARS = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
def name4(b, pos):
    if pos+4 > len(b):
        return None
    seg = b[pos:pos+4]
    for c in seg:
        if c not in NAME_CHARS:
            return None
    return seg.decode('ascii')

def ascii_strings(buf, minlen=4):
    out, cur, start = [], [], 0
    for i, c in enumerate(buf):
        if 32 <= c < 127:
            if not cur:
                start = i
            cur.append(chr(c))
        else:
            if len(cur) >= minlen:
                out.append((start, ''.join(cur)))
            cur = []
    if len(cur) >= minlen:
        out.append((start, ''.join(cur)))
    return out

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'dsdt.bin'
    want = sys.argv[2].split(',') if len(sys.argv) > 2 else ['MLR1','MLR2','MOFD']
    with open(path, 'rb') as f:
        b = f.read()
    print("file=%s  size=%d  sig=%s" % (path, len(b), b[0:4].decode('ascii','replace')))

    hits = []
    i = 0x24
    while i < len(b) - 8:
        op = b[i]
        if op in (0x08, 0x14, 0x10):
            nm = name4(b, i+1)
            if nm:
                off = i + 1 + 4
                if op == 0x14:
                    pass  # arg count follows pkglen
                try:
                    pl, hb = pkglen(b, off)
                except IndexError:
                    i += 1; continue
                end = i + pl          # PkgLength counts from the PkgLength field itself
                if 8 <= pl <= len(b) and end <= len(b) and end > off:
                    kind = {0x08:'Name', 0x14:'Method', 0x10:'Scope'}[op]
                    argc = None
                    if op == 0x14:
                        if off + hb < len(b):
                            argc = b[off + hb]
                    hits.append((i, end, kind, nm, pl, argc))
                    i = end
                    continue
        i += 1

    print("total objects=%d" % len(hits))
    print()
    for name in want:
        print("=" * 78)
        print("### %s" % name)
        found = [h for h in hits if h[3] == name]
        if not found:
            print("  (no Name/Method/Scope definition found)")
        for (s, e, kind, nm, pl, argc) in found:
            body = b[s:e]
            print("  %s @ 0x%06X  pkg=%d bytes  argc=%s" % (kind, s, pl, argc))
            # hexdump 16/line
            for o in range(0, len(body), 16):
                chunk = body[o:o+16]
                hexs = ' '.join('%02X' % c for c in chunk)
                asc  = ''.join(chr(c) if 32 <= c < 127 else '.' for c in chunk)
                print("    0x%06X  %-47s  %s" % (s+o, hexs, asc))
            strs = ascii_strings(body, 4)
            if strs:
                print("    -- strings --")
                for (so, sv) in strs:
                    print("       +0x%03X: %s" % (so, sv))
            print()

    # 顺带把所有对象的名字列出来，方便找邻居
    print("=" * 78)
    print("### all objects in 0x7A000..0x7B400 (LPCB/EC0 namespace)")
    for (s, e, kind, nm, pl, argc) in hits:
        if 0x7A000 <= s <= 0x7B400:
            print("  0x%06X  %-6s %-6s pkg=%d argc=%s" % (s, kind, nm, pl, argc))

if __name__ == '__main__':
    main()
