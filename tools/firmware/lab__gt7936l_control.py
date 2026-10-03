# -*- coding: utf-8 -*-
"""关键对照：真明文的 Goodix 固件（GT7936L, BERLIN 族）里有没有代码？"""
import struct, collections, math, zlib
from capstone import *
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
def cov(b, lim=65536):
    off = ok = 0
    for ins in md.disasm(b[:lim], 0):
        if ins.address != off: break
        off += ins.size; ok += 1
    return ok * 2 / lim * 100, ok / (lim / 2)
def half8(b):
    ev = collections.Counter(b[0::2]); od = collections.Counter(b[1::2])
    f = lambda c, n: sum(sorted(c.values(), reverse=True)[:8]) / max(n,1) * 100
    return (f(ev, len(b[0::2])) + f(od, len(b[1::2]))) / 2
gl = open("vendor/goodix-lvfs/GT7936L_16753412.bin", 'rb').read()
print("=== GT7936L（LVFS 2026，BERLIN 族，自称明文）逐段指令集指纹 ===")
print("%-20s %-8s %-9s %-11s %-10s %s" % ("区段", "H0", "零%", "Thumb覆盖%", "半字top8%", "判定"))
for lo, hi in [(0,0x400),(0x400,0x1000),(0x1000,0x8000),(0x8000,0x20000),(0x20000,0x30000),(0x30000,len(gl))]:
    seg = gl[lo:hi]
    if len(seg) < 0x100: continue
    c = collections.Counter(seg)
    h0 = -sum(v/len(seg)*math.log2(v/len(seg)) for v in c.values())
    t, _ = cov(seg, min(len(seg), 0x8000))
    print("%-20s %-8.4f %-9.1f %-11.1f %-10.1f %s"
          % ("0x%05X-0x%05X" % (lo, hi), h0, 100*seg.count(0)/len(seg), t, half8(seg),
             "★含代码" if t > 50 else ("空白" if h0 < 4 else "数据")))
print()
print("=== 对照表：真明文固件 vs 载荷A 明文 ===")
K = open("<WORKSPACE>",'rb').read()
K316 = K[316:]+K[:316]
import sys
sys.path.insert(0, "poc/decrypt-v2")
d = open("bios-re/GT7868Q_native_fw.bin",'rb').read()
def parse(buf):
    for o in range(0, min(len(buf)-300, 65536)):
        s = struct.unpack('>I', buf[o:o+4])[0]
        if 1000 < s <= len(buf)-o and sum(buf[o+6:o+6+s]) & 0xFFFF == struct.unpack('>H', buf[o+4:o+6])[0]:
            ent=[]
            for i in range(30):
                q=o+0x20+i*8; t=buf[q]; ln=int.from_bytes(buf[q+1:q+5],'big')
                if t==0 and ln==0: break
                ent.append((t,ln))
            return o,ent
o,ent=parse(d); off=o+0x100; ALL=b""
for i,(t,ln) in enumerate(ent):
    xr=d[off:off+ln]; off+=ln
    ALL += bytes(v^K316[(k+0x100)%1024] for k,v in enumerate(xr))
c=collections.Counter(ALL)
print("  载荷A 明文全量(100,352B): H0=%.4f 零%.1f%% zlib=%.4f Thumb覆盖=%.1f%% 半字top8=%.1f%%"
      % (-sum(v/len(ALL)*math.log2(v/len(ALL)) for v in c.values()),
         100*ALL.count(0)/len(ALL), len(zlib.compress(ALL,9))/len(ALL), cov(ALL)[0], half8(ALL)))
c=collections.Counter(gl)
print("  GT7936L 全量(258,128B) : H0=%.4f 零%.1f%% zlib=%.4f Thumb覆盖=%.1f%% 半字top8=%.1f%%"
      % (-sum(v/len(gl)*math.log2(v/len(gl)) for v in c.values()),
         100*gl.count(0)/len(gl), len(zlib.compress(gl,9))/len(gl), cov(gl,0x10000)[0], half8(gl)))
