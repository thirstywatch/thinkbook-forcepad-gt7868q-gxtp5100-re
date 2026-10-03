# -*- coding: utf-8 -*-
"""cfg 语义路线 step2：每个 ID 的 payload 是否 = 「计数字段 + 数组」？
   对每个 payload 穷举候选布局，并要求【跨两个机型一致】才认定为该布局。"""
import os, collections

CFG = r"<WORKSPACE>"
FILES = [("sid0", "sid0.bin"), ("sid3", "sid3.bin")]

def walk(buf, st=0x40):
    i = st; out = []
    while i + 2 <= len(buf):
        ln = buf[i]; tag = buf[i+1]
        if ln < 2 or i + ln > len(buf):
            out.append((i, tag, ln, None)); break
        out.append((i, tag, ln, buf[i+2:i+ln])); i += ln
    return out

def hyps(pl):
    """返回该 payload 满足的所有布局假设"""
    n = len(pl); out = []
    if n == 0: return ["空"]
    def cnt(m):
        if n - m <= 0: return None
        if pl[0] == n - m:      # 1 字节计数 + 后续按 1 字节
            return ("u8=计数×1B", pl[0])
        return None
    # u8 计数
    for w, nm in ((1, 'u8'), (2, 'u16LE'), (2, 'u16BE')):
        for hsz in (1, 2):
            if n <= hsz: continue
            if hsz == 1:
                c = pl[0]; v = None
            else:
                c = int.from_bytes(pl[:2], 'little') if nm == 'u16LE' else int.from_bytes(pl[:2], 'big')
            body = n - hsz
            if c and body % c == 0 and 1 <= body // c <= 4 and c <= 300:
                out.append("%s计数=%d × %dB" % (nm, c, body // c))
    # 无计数字段的纯数组
    if n % 2 == 0:
        v = [int.from_bytes(pl[i:i+2], 'little') for i in range(0, n, 2)]
        near = sum(1 for x in v if 120 <= x <= 136) / len(v)
        asc = all(v[i] <= v[i+1] for i in range(len(v)-1))
        if near > 0.6: out.append("纯 u16LE ×%d（%d%%∈[120,136]）" % (len(v), near*100))
        if asc and len(v) >= 4: out.append("纯 u16LE ×%d（单调↑）" % len(v))
        vb = [int.from_bytes(pl[i:i+2], 'big') for i in range(0, n, 2)]
        nearb = sum(1 for x in vb if 120 <= x <= 136) / len(vb)
        if nearb > 0.6: out.append("纯 u16BE ×%d（%d%%∈[120,136]）" % (len(vb), nearb*100))
    # u8 计数 + u16 数组（计数为元素个数）
    if len(pl) >= 2 and 1 <= pl[0] <= 300:
        if (n - 1) == pl[0]*2: out.append("u8计数=%d × u16" % pl[0])
        if (n - 2) == pl[0]*2: out.append("u16计数=%d × u16" % pl[0])
    if pl[0] == n - 1: out.append("u8计数=%d × u8" % pl[0])
    return list(dict.fromkeys(out)) or ["无匹配"]

data = {}
for nm, fn in FILES:
    d = open(os.path.join(CFG, fn), 'rb').read()
    data[nm] = {x[1]: x[3] for x in walk(d) if x[3] is not None}

ids = sorted(set(data['sid0']) | set(data['sid3']))
print("%-5s %-6s %-6s %-10s %s" % ("ID", "sid0长", "sid3长", "共有的布局", "各自假设"))
for t in ids:
    a = data['sid0'].get(t); b = data['sid3'].get(t)
    ha = hyps(a) if a is not None else []
    hb = hyps(b) if b is not None else []
    common = [x for x in ha if x in hb]
    mark = "★一致" if common else ""
    print("%-5s %-6s %-6s %-10s %s %s | %s" %
          ("0x%02X" % t, len(a) if a is not None else '-', len(b) if b is not None else '-',
           ",".join(common) or '—', mark, "; ".join(ha), "; ".join(hb)))
