# -*- coding: utf-8 -*-
"""把 [LEN u8][TAG u8][payload] 这套（在 tpcfgsid0 上已验证）套到文件配置体(1024 B)上"""
import os, struct, zlib, collections

LAB = r"<LAB>\touchpad-lab"
d = open(os.path.join(LAB, "bios-re", "GT7868Q_native_fw.bin"), 'rb').read()
BODY = d[0x4C:0x4C+1024]
DEV = open(os.path.join(LAB, "poc", "device-96F8.bin"), 'rb').read() if os.path.exists(
    os.path.join(LAB, "poc", "device-96F8.bin")) else None

def walk(buf, st):
    i = st; out = []
    while i + 2 <= len(buf):
        ln = buf[i]; tag = buf[i+1]
        if ln < 2 or i + ln > len(buf):
            out.append((i, tag, ln, None)); break
        out.append((i, tag, ln, buf[i+2:i+ln])); i += ln
    return out

def report(buf, name, st=0):
    w = walk(buf, st)
    used = sum(x[2] if x[3] is not None else 0 for x in w)
    tags = [x[1] for x in w if x[3] is not None]
    asc = sum(1 for a, b in zip(tags, tags[1:]) if b > a) / max(1, len(tags)-1)
    print("### %s  长 %d  起点 %d  块数 %d  覆盖 %.1f%%  TAG严格递增比 %.2f" %
          (name, len(buf), st, len(w), used/len(buf)*100, asc))
    print("%-6s %-5s %-5s %-6s %s" % ("偏移", "LEN", "TAG", "paylen", "payload(40B)"))
    for off, tag, ln, pl in w:
        if pl is None:
            print("%-6s 0x%02X  0x%02X  %-6s <TRUNC>" % (hex(off), ln, tag, "")); break
        s = pl[:40].hex(' ')
        if len(pl) > 40: s += " …"
        print("%-6s 0x%02X  0x%02X  %-6d %s" % (hex(off), ln, tag, len(pl), s))
    return [x[1] for x in w if x[3] is not None]

print("=" * 78)
t_body = report(BODY, "文件配置体 (0x4C 起 1024 B)", 0)
print()
print("=" * 78)
# 也试起点 2、4（跳过 2 字节）
for st in (1, 2, 4):
    w = walk(BODY, st)
    used = sum(x[2] if x[3] is not None else 0 for x in w)
    tags = [x[1] for x in w if x[3] is not None]
    asc = sum(1 for a, b in zip(tags, tags[1:]) if b > a) / max(1, len(tags)-1)
    print("起点 %d: 块数 %d 覆盖 %.1f%% 递增比 %.2f 前 12 个 TAG %s" %
          (st, len(w), used/len(BODY)*100, asc, [hex(x) for x in tags[:12]]))
print()
print("=" * 78)
print("### 对照：tpcfgsid0 的 TAG 序列（起点 0x40）")
s0 = open(r"<WORKSPACE>", 'rb').read()
t_sid0 = [x[1] for x in walk(s0, 0x40) if x[3] is not None]
print("  sid0 前 30 个 TAG:", [hex(x) for x in t_sid0[:30]])
print("  配置体 前 30 个 TAG:", [hex(x) for x in t_body[:30]])
print()
print("  两者共有的 TAG 数:", len(set(t_sid0) & set(t_body)), "/ sid0", len(set(t_sid0)), "/ 体", len(set(t_body)))
print("  sid0 有、体无:", [hex(x) for x in sorted(set(t_sid0) - set(t_body))])
print("  体有、sid0 无:", [hex(x) for x in sorted(set(t_body) - set(t_sid0))])
