# -*- coding: utf-8 -*-
"""配置体(1024 B) 帧格式的穷举判定：试 [LEN][TAG] / [TAG][LEN] / u16 变体，含打乱对照"""
import os, random, collections

LAB = r"<LAB>\touchpad-lab"
d = open(os.path.join(LAB, "bios-re", "GT7868Q_native_fw.bin"), 'rb').read()
BODY = d[0x4C:0x4C+1024]

def mk_walker(lt, lsz, tsz):
    """lt='len_first'/'tag_first'; lsz/tsz in (1,2)"""
    def w(buf, st):
        i = st; out = []
        while i + lsz + tsz <= len(buf):
            if lt == 'len_first':
                ln = int.from_bytes(buf[i:i+lsz], 'little')
                tag = int.from_bytes(buf[i+lsz:i+lsz+tsz], 'little')
            else:
                tag = int.from_bytes(buf[i:i+tsz], 'little')
                ln = int.from_bytes(buf[i+tsz:i+tsz+lsz], 'little')
            tot = lsz + tsz + ln
            if ln == 0 or i + tot > len(buf):
                out.append((i, tag, ln, None)); break
            out.append((i, tag, ln, buf[i+lsz+tsz:i+tot])); i += tot
        return out
    return w

FMTS = {}
for lt in ('len_first', 'tag_first'):
    for lsz in (1, 2):
        for tsz in (1,):
            FMTS["%s L%d T%d" % (lt, lsz, tsz)] = mk_walker(lt, lsz, tsz)

def evalw(buf, st, wfn):
    w = wfn(buf, st)
    used = sum(x[2] + (1 if wfn.__name__ == '' else 0) for x in w if x[3] is not None)
    tags = [x[1] for x in w if x[3] is not None]
    trunc = any(x[3] is None for x in w)
    asc = sum(1 for a, b in zip(tags, tags[1:]) if b > a) / max(1, len(tags)-1)
    return used, w, tags, trunc, asc

print("### 配置体 1024 B —— 帧格式穷举（覆盖率 vs 打乱对照，以及 TAG 递增性）")
for fname, wfn in FMTS.items():
    best = None
    for st in range(0, 64):
        used, w, tags, trunc, asc = evalw(BODY, st, wfn)
        if best is None or used > best[0]:
            best = (used, st, w, tags, trunc, asc)
    used, st, w, tags, trunc, asc = best
    # 打乱对照：同样扫起点取最优
    nulls = []
    for _ in range(20):
        y = bytearray(BODY); random.shuffle(y)
        nulls.append(max(evalw(bytes(y), s, wfn)[0] for s in range(0, 64)) / len(BODY))
    nm = sum(nulls)/len(nulls)
    print("  %-16s 起点 %-3d 覆盖 %5.1f%%  对照 %5.1f%%  Δ=%+6.1f pt  块数 %-4d 截断 %-5s 递增比 %.2f"
          % (fname, st, used/len(BODY)*100, nm*100, (used/len(BODY)-nm)*100, len(w), trunc, asc))
    if st == 0 and used/len(BODY) > 0.5:
        print("       前 12 块 TAG:", [hex(t) for t in tags[:12]])

print()
print("### 配置体前 64 字节逐字节")
for i in range(0, 64, 16):
    print("  +%03X  %-47s  %s" % (i, " ".join("%02x" % c for c in BODY[i:i+16]),
          "".join(chr(c) if 32 <= c < 127 else '.' for c in BODY[i:i+16])))

print()
print("### 设备 0x96F8 区（离线副本）与文件配置体 是否逐字节相同")
print("  说明：二者本应相同（§19.13.3(d) 说法）")
dev = d[0x4C:0x4C+32]
print("  体前 32 B:", dev.hex(' '))
