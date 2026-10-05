# -*- coding: utf-8 -*-
"""R12-2 ★★★★ 用「已知答案」的样本解格式：3 份真实手机 cfg 包（GT9916/Berlin）
   已知：dubai-csot 的 1080x2400 @0x12b、manet 的 1440x3200 @0x12b、cybert 的 1220x2712 @0x143
   若这三处的【周边结构】与本机 cfg 的 +0x10E 一带同构，就能直接定案本机那段的格式。
"""
import os

def ihex(t):
    out = {}
    for ln in t.splitlines():
        ln = ln.strip()
        if not ln.startswith(':'): continue
        n = int(ln[1:3], 16); a = int(ln[3:7], 16); ty = int(ln[7:9], 16)
        if ty == 0: out[a] = bytes.fromhex(ln[9:9+2*n])
    if not out: return b''
    hi = max(out); buf = bytearray(hi + len(out[hi]))
    for a, dd in out.items(): buf[a:a+len(dd)] = dd
    return bytes(buf)

F = {f: open(f, 'rb').read() for f in sorted(os.listdir('.'))}
S = {k: (ihex(v.decode('ascii', 'ignore')) if v[:1] == b':' else v) for k, v in F.items()}

for k, d in S.items():
    print('=' * 96)
    print('###', k, len(d), 'B')
    d0 = d[0] | (d[1] << 8) | (d[2] << 16) | (d[3] << 24)
    print('  head: bin_len=%d  文件长=%d  checksum_ok=%s  pkg_num=%d'
          % (d0, len(d), (sum(d[5:]) & 0xFF) == d[4], d[9]))
    # 头 16 B + 偏移表
    pn = d[9]
    tbl = [d[16+2*i] | (d[17+2*i] << 8) for i in range(pn)]
    print('  pkg 偏移表:', [hex(x) for x in tbl])
    for pi, off in enumerate(tbl):
        CONST = 56; REG = 65
        ic = d[off:off+16].split(b'\x00')[0].decode('latin1')
        hwp = d[off+16:off+28].split(b'\x00')[0].decode('latin1')
        print('   pkg%d @%#x  ic_type=%r  hw_pid=%r' % (pi, off, ic, hwp))
        cstart = off + CONST + REG
        # 找 x/y 分辨率（u16LE 相邻对，值域 900..3400）
        hits = []
        for i in range(cstart, len(d) - 3):
            a = d[i] | (d[i+1] << 8); b = d[i+2] | (d[i+3] << 8)
            if 900 <= a <= 3400 and 900 <= b <= 3400:
                hits.append((i - cstart, i, a, b))
        print('   cfg 数据起点 %#x  候选相邻 LE 对 %d 个: %s' % (cstart, len(hits), [(hex(o), a, b) for o, _, a, b in hits[:8]]))
        if hits:
            o0, i0, a0, b0 = hits[0]
            print('   ★ 以 cfg 数据 +%#x 为中心，前后各 24 B（cfg 是结构体外的【寄存器像】？）' % o0)
            s = max(cstart, i0 - 24); e = min(len(d), i0 + 32)
            for r in range(s, e, 16):
                b_ = d[r:r+16]
                print('      %#08x  %s  |%s|' % (r, ' '.join('%02x' % x for x in b_),
                                                 ''.join(chr(x) if 32 <= x < 127 else '.' for x in b_)))
    print('  寄存器映射区（官方 pkg_reg_info）原文:')
    off = tbl[0]
    raw = d[off+CONST:off+CONST+REG]
    txt = raw.decode('latin1')
    import re
    print('   ', ' | '.join(x.strip() for x in txt.split('\x00') if x.strip())[:400])
