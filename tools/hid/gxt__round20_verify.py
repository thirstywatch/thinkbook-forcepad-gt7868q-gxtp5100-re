# -*- coding: utf-8 -*-
# 第二十轮：独立复现子代理的三条"推翻"（不能盲信，逐条自验）
# 推翻1: 分区表结构应为 [type][pad][size:be16][page:be16]（单位 0x1000），不是 type+be32+be32
# 推翻2: 0x00000-0x01200 不是 8051 代码，是配置/参数表
# 推翻3: "4 张零差 1024 B 表"不成立，实为 3 组 512 B 块 + XOR 掩码
import struct, os
from collections import Counter

P = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
D = open(P, 'rb').read()
OUT = []
def w(s=''):
    OUT.append(s)

w("="*78)
w("第二十轮：独立复现子代理的三条推翻（自验）")
w("="*78)

# ============ 推翻1：分区表结构 ============
w()
w("### 推翻1 复现：分区表结构")
w()
w("【假设A】原结构 type:u8 + size:be32 + addr:be32（每项 8 B，从 0x1164 起）")
tbl_off = 0x1164
w("  偏移       原结构解读（type / size / addr）")
alignA = 0
for i in range(12):
    off = tbl_off + i*8
    b = D[off:off+8]
    typ = b[0]
    size = int.from_bytes(b[1:5], 'big')
    addr = int.from_bytes(b[5:9], 'big') if off+9 <= len(D) else int.from_bytes(b[4:8], 'big')
    # 修正：应为 b[1:5]=size, b[5:9]=addr，但每项 8B 则只有 b[1:5] 和 b[5:8]?
    # 按 8B/项：type + 4B size + 3B addr? 先按报告说法试
    w("   0x%05X   %02x / %10d(0x%X) / %10d(0x%X)  addr对齐0x1000=%s"
      % (off, typ, size, size, addr, addr, (addr % 0x1000 == 0)))
    if addr % 0x1000 == 0:
        alignA += 1
w("  ⇒ addr 0x1000 对齐率 %d/12 = %.3f" % (alignA, alignA/12))

w()
w("【假设B】子代理结构 [type:u8][pad:u8][size:be16][page:be16]（单位 0x1000）")
alignB = 0
rowsB = []
for i in range(12):
    off = tbl_off + i*8
    b = D[off:off+8]
    typ = b[0]; pad = b[1]
    size16 = int.from_bytes(b[2:4], 'big')
    page16 = int.from_bytes(b[4:6], 'big')
    size = size16 * 0x1000
    page = page16 * 0x1000
    ok = (page % 0x1000 == 0) and (size % 0x1000 == 0)
    if ok: alignB += 1
    rowsB.append((i, typ, pad, size16, page16, size, page))
    w("   #%-2d 0x%05X  type=%02x pad=%02x size16=%5d page16=%5d  => size=0x%06X page=0x%06X"
      % (i, off, typ, pad, size16, page16, size, page))
w("  ⇒ 对齐率 %d/12 = %.3f" % (alignB, alignB/12))

# 检查是否无重叠 + 覆盖率
w()
w("  无重叠检验（按 page 排序）：")
srt = sorted(rowsB, key=lambda r: r[6])
prev_end = -1
overlap = 0
for r in srt:
    s, e = r[6], r[6] + r[5]
    if s < prev_end:
        overlap += 1
        w("    ⚠ #%d page=0x%X size=0x%X 与前一区重叠" % (r[0], s, r[5]))
    prev_end = max(prev_end, e)
w("    重叠数: %d" % overlap)
tot = sum(r[5] for r in rowsB)
w("    size 总和 = 0x%X = %d B" % (tot, tot))
w("    并集终点 = 0x%X" % max(r[6]+r[5] for r in rowsB))
w()
w("  【关键判别】两种假设谁对？看 pad 字节是否恒为 0，以及 page16 是否单调：")
w("    pad 字节序列: %s" % ' '.join('%02x' % r[2] for r in rowsB))
w("    page16 序列 : %s" % ' '.join('%d' % r[4] for r in rowsB))

# 更强的判别：page16 是否恰好构成小端序的合理值
w()
w("  【第三种可能】按小端读：type:u8 + pad:u8 + size:le16 + page:le16")
for i in range(4):
    off = tbl_off + i*8
    b = D[off:off+8]
    sz = int.from_bytes(b[2:4],'little'); pg = int.from_bytes(b[4:6],'little')
    w("   #%d 0x%05X  %s  -> sz16=%d(0x%X) pg16=%d(0x%X)  => 0x%X / 0x%X"
      % (i, off, ' '.join('%02x'%x for x in b), sz, sz, pg, pg, sz*0x1000, pg*0x1000))

# ============ 推翻2：0x00000-0x01200 是不是 8051 ============
w()
w("### 推翻2 复现：0x00000-0x01200 的性质")
seg = D[0:0x1200]
w("  长度 %d B，熵 %.4f，零占比 %.4f" % (
    len(seg),
    -sum((v/len(seg))*__import__('math').log2(v/len(seg)) for v in Counter(seg).values()),
    seg.count(0)/len(seg)))

w()
w("  8051 判据（本项目已在真 8051 代码上标定过的相对跳转集中度 |rel|<=8）：")
SJMP=0x80; JREL={0x70,0x60,0x50,0x40,0x38,0x30,0x28,0x20,0x78,0x68,0x58,0x48,0x18,0x10,0x08,0xD8,0xC8,0xB8,0xA8,0x98,0x88}
def relstat(buf):
    vals=[]
    for i in range(len(buf)-1):
        if buf[i]==SJMP or buf[i] in JREL:
            r=buf[i+1]
            if r>=128: r-=256
            vals.append(r)
    if not vals: return None,0
    return sum(1 for v in vals if abs(v)<=8)/len(vals), len(vals)
r,n = relstat(seg)
w("    0x00000-0x01200: rel=%.3f (n=%d)   [真8051=0.558, 数据基线=0.067]" % (r,n))
r2,n2 = relstat(D[0x19A00:0x19A00+4608])
w("    0x19A00 (已知ARM) : rel=%.3f (n=%d)" % (r2,n2))

w()
w("  子代理说的「单调递增字节串」复核 —— 直接找 00 01 02 04 05 06 0C 0D 0E 0F 10 ... ：")
needle = bytes([0x00,0x01,0x02,0x04,0x05,0x06,0x0C,0x0D,0x0E,0x0F,0x10,0x11,0x12,0x13])
pos = D.find(needle)
w("    命中偏移: %s" % ('0x%05X'%pos if pos>=0 else '未找到'))
if pos >= 0:
    start = max(0, pos-16)
    for off in range(start, pos+48, 16):
        w("      0x%05X  %-47s  %s" % (off, ' '.join('%02x'%b for b in D[off:off+16]),
          ''.join(chr(b) if 32<=b<127 else '.' for b in D[off:off+16])))

# 8051 关键操作码密度（真 8051 代码应有明显富集）
w()
w("  8051 关键操作码密度（/KB）：")
for nm, buf in [('0x00000-0x01200', D[0:0x1200]),
                ('0x19A00 ARM区', D[0x19A00:0x19A00+0x1200]),
                ('随机对照', os.urandom(0x1200))]:
    n = len(buf)
    ops = {'0x75(MOV dir,#imm)': buf.count(0x75),
           '0x12(LCALL)': buf.count(0x12),
           '0x22(RET)': buf.count(0x22),
           '0x80(SJMP)': buf.count(0x80),
           '0xE0(MOVX A,@DPTR)': buf.count(0xE0),
           '0x90(MOV DPTR,#imm16)': buf.count(0x90)}
    w("    %-18s %s" % (nm, '  '.join('%s=%d'%(k.split('(')[0],v) for k,v in ops.items())))

# ============ 推翻3：重复块 ============
w()
w("### 推翻3 复现：重复块的真实结构")
# 找所有 512B 块的重复
w("  512 B 块重复统计（0x01200-0x19000 范围内，按块内容分组）：")
region = D[0x01200:0x19000]
groups = {}
for off in range(0, len(region)-512, 512):
    blk = region[off:off+512]
    groups.setdefault(blk, []).append(0x01200+off)
dups = {k:v for k,v in groups.items() if len(v) > 1}
w("    有重复的 512B 块组数: %d" % len(dups))
for k,v in sorted(dups.items(), key=lambda x:-len(x[1]))[:10]:
    w("      x%-2d  %s" % (len(v), ' '.join('0x%05X'%o for o in v)))

w()
w("  子代理声称：x8 组在 0x3800,0x5800,0x8800,0x8C00,0x9000,0x9400,0x9800,0xF800")
w("  ⇒ 这些地址的 512B 块是否真的相同？")
for a,b in [(0x8800,0x8C00),(0x8C00,0x9000),(0x9000,0x9400),(0x3800,0x5800),(0x8800,0xF800)]:
    ba, bb = D[a:a+512], D[b:b+512]
    diff = sum(1 for x,y in zip(ba,bb) if x!=y)
    w("    0x%05X vs 0x%05X : 不同字节数 %d/512  %s" % (a,b,diff, '★零差' if diff==0 else ''))

w()
w("  子代理声称：A = B XOR mask, mask=[0x20,0x02,0x04,0x80]（周期4）")
mask = bytes([0x20,0x02,0x04,0x80])
for a,b in [(0x8800,0x8C00),(0x8C00,0x9000),(0x9000,0x9400),(0x3800,0x5800),(0x3800,0xF800)]:
    ba, bb = D[a:a+512], D[b:b+512]
    xored = bytes(x ^ mask[i%4] for i,x in enumerate(bb))
    diff = sum(1 for x,y in zip(ba,xored) if x!=y)
    w("    0x%05X vs (0x%05X ^ mask) : 不同 %d/512  %s" % (a,b,diff,'★成立' if diff==0 else ''))

w()
w("  ★ 独立检验：这个 mask 关系在别处是否也成立？（若只在少数对上成立就是巧合）")
hits = 0; tests = 0
for i in range(0, len(region)-512, 512):
    for j in range(i+512, min(i+0x8000, len(region)-512), 512):
        tests += 1
        if D[0x01200+j:0x01200+j+512] == bytes(D[0x01200+x] ^ mask[(x-i)%4] for x in range(i, i+512)):
            hits += 1
w("    region 内 512B 块对 随机采样 %d 对，满足 XOR-mask 关系 %d 对" % (tests, hits))

open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cfg_parsed', 'round20_verify.txt'), 'w', encoding='utf-8').write('\n'.join(OUT))
print('\n'.join(OUT))
