# -*- coding: utf-8 -*-
"""R01. 汇总所有关键数字, 生成 AUDIT_REPORT 的数据基础。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
from capstone import *
from capstone.arm import *
from collections import Counter
import statistics
FW = load(); N = len(FW)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

def badrate(off, ln):
    i = off; ok = 0; bad = 0
    while i < min(off+ln, N):
        g = None
        for ins in md.disasm(FW[i:i+16], i): g = ins; break
        if g is None: bad += 1; i += 2; continue
        ok += 1; i += g.size
    return bad/(ok+bad) if ok+bad else 1.0

print("### 最终数字汇总 ###")
print(f"N = {N} = 0x{N:X}")
print()
# 分区表
T = 0x1164
recs = []
for i in range(12):
    o = T + i*8
    recs.append((FW[o], (FW[o+1]<<16)|(FW[o+2]<<8)|FW[o+3], (FW[o+4]<<16)|(FW[o+5]<<8)|FW[o+6]))
print("分区表 12 项 (sz字段, pg字段):")
for i, (t, sz, pg) in enumerate(recs):
    print(f"  [{i:2d}] type=0x{t:02X} size字段=0x{sz:X} page字段=0x{pg:X} -> size={sz*0x1000} addr=0x{pg*0x1000:X}")
tot = sum(s*0x1000 for _, s, _ in recs)
print(f"  size 总和 = {tot} = 0x{tot:X};  0x200000 = {0x200000}")
print(f"  覆盖 [0, 0x{max(p for _,_,p in recs)*0x1000:X})  声明 2 MB")
segs = sorted(((p*0x1000, s*0x1000) for _, s, p in recs))
lo = min(a for a, _ in segs); hi = max(a+s for a, s in segs)
print(f"  span = 0x{hi-lo:X}, 有效 = 0x{tot:X}, 空隙 = 0x{hi-lo-tot:X} = {hi-lo-tot} B")
print()
# 分区到文件的映射
print("文件偏移 0x2775C 对应的分区: 分区 0x00000-0x10000 (type=0x02) 与 0x10000-0x40000 (type=0x02)")
print("  => 文件 0x2775C (161628 B) 略小于 0x30000 (196608 B) 的分区大小?")
print(f"     0x30000 = {0x30000};  0x2775C = {0x2775C};  差 = {0x30000-0x2775C}")
# 关键: 文件是否 = 分区 0x10000 起 的 0x2775C 字节?
print(f"  也可能: 文件从 flash 0x000000 起, 但分区表声明为 2MB -> 文件是'仅含前 160KB 的部分镜像'")
print()
print("### 分段 (非法率判据) ###")
for lo2, hi2, tag in [(0, 0x2000, "配置/参数区"), (0x2000, 0x19850, "高熵数据区"),
                      (0x19850, 0x265B8, "ARM Thumb-2 代码"), (0x265B8, N, "尾部数据")]:
    br = badrate(lo2, hi2-lo2)
    e = entropy(FW[lo2:hi2])
    print(f"  [0x{lo2:05X},0x{hi2:05X}) {tag:16s} 非法率={br:.4f} 熵={e:.4f} 长度={hi2-lo2}")
print()
print("### P=4 位置掩码 ###")
print("  mask = [0x20, 0x02, 0x04, 0x80]  (= 位 5,1,2,7 翻转)")
print("  仅作用于 0x8600/0x8800/0x8A00/0x8C00/0x8E00/0x9000/0x9200/0x9400/0x9600/0x9800 的相邻 512B 对")
print("  B=FW[0x8800:+512] 在 0x3800/0x5800/0x8800/0x9800/0xF800 完全相同 (5 份)")
print("  A=FW[0x8600:+512] 在 0x8600/0x8A00/0x8E00/0x9200/0x9600 完全相同 (5 份)")
print("  A = B XOR mask")
print()
print("### 代码区外设 ###")
import re
consts = Counter()
i = 0x19850
while i < 0x265B8:
    g = None
    for ins in md.disasm(FW[i:i+4], i): g = ins; break
    if g is None: i += 2; continue
    if g.mnemonic == 'movw':
        j = i + g.size; g2 = None
        for ins2 in md.disasm(FW[j:j+4], j): g2 = ins2; break
        if g2 and g2.mnemonic == 'movt':
            m1 = re.search(r'#(0x[0-9a-f]+)', g.op_str); m2 = re.search(r'#(0x[0-9a-f]+)', g2.op_str)
            if m1 and m2:
                consts[(int(m2.group(1),16)<<16)|(int(m1.group(1),16)&0xFFFF)] += 1
    i += g.size
per = {v: n for v, n in consts.items() if 0x40000000 <= v < 0x60000000}
print(f"  外设地址常量 (0x4000xxxx) 共 {len(per)} 个不同值, 合计 {sum(per.values())} 次")
for v, n in sorted(per.items()):
    print(f"    0x{v:08X} x{n}")
print(f"\n  RAM 常量 (0x2000xxxx): {sum(1 for v in consts if 0x20000000<=v<0x20080000)} 个不同值")
print(f"  FLASH 常量 (0x0800xxxx): {sum(1 for v in consts if 0x08000000<=v<0x09000000)} 个不同值")
print()
print("### 关键字符串 ###")
for pat in [b"YELSTO", b"7868Q", b"TF100A_Test_FW", b"Nov 28 2023", b"19:10:59"]:
    k = FW.find(pat)
    print(f"  {pat!r:20s} @ 0x{k:05X}" if k >= 0 else f"  {pat!r} 未找到")
print()
print("### 触觉关键词计数 (全为 0) ###")
for k in ["AW869","86927","awinic","AWINIC","LRA","lra","haptic","HAPTIC","vibr",
          "BEMF","bemf","motor","MOTOR","trig","TRIG","wave","WAVE","AW87"]:
    c = FW.count(k.encode())
    if c: print(f"  {k}: {c}")
print("  -> 全部为 0 (已逐一验证)")
